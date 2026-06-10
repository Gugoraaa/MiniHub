import re

from mininet.net import Mininet
from mininet.node import OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel

from sites.tiendaSanPedro import TiendaSanPedro

# ── colores ──────────────────────────────────────────────────────────────────
BOLD  = '\033[1m'
CYAN  = '\033[96m'
GREEN = '\033[92m'
RED   = '\033[91m'
RESET = '\033[0m'

# (host, vlan, gateway, label, dhcp_prefix, dhcp_cidr)
SP_VLAN_HOSTS = [
    ('sp_hwifi',  130, '10.3.0.1',   'WiFi',       '10.3.0.',  24),
    ('sp_hchk',   140, '10.3.1.1',   'Checkout',   '10.3.1.',  27),
    ('sp_hadmin',  40, '10.3.1.33',  'Admin',      '10.3.1.',  29),
    ('sp_hsec',    30, '10.3.1.41',  'Security',   '10.3.1.',  29),
    ('sp_hcam',   100, '10.3.1.49',  'Camaras',    '10.3.1.',  25),
    ('sp_hprint', 110, '10.3.1.113', 'Impresoras', '10.3.1.',  28),
    ('sp_hphone', 120, '10.3.1.129', 'Telefonos',  '10.3.1.',  29),
]


# ── helpers locales ───────────────────────────────────────────────────────────

def section(title):
    print(f'\n{BOLD}{CYAN}=== {title} ==={RESET}')


def ok(label):
    print(f'{GREEN}[OK]{RESET}   {label}')


def fail(label, detail=''):
    print(f'{RED}[FAIL]{RESET} {label}')
    if detail:
        print(f'{RED}{detail.strip()}{RESET}')


def sp_node(net, name):
    try:
        return net.get(name)
    except Exception as e:
        fail(f'Nodo {name} no encontrado', str(e))
        return None


def sp_ping(net, src_name, dst_ip, label):
    h = sp_node(net, src_name)
    if h is None:
        return False
    out = h.cmd(f'ping -c 3 -W 1 {dst_ip}')
    if '0% packet loss' in out:
        ok(label)
        return True
    fail(label, out)
    return False


def sp_process_running(net, host_name, pattern, label):
    h = sp_node(net, host_name)
    if h is None:
        return False
    out = h.cmd(f"ps aux | grep '{pattern}' | grep -v grep")
    if out.strip():
        ok(label)
        return True
    fail(label, f'No se encontro proceso: {pattern}')
    return False


def sp_svi_has_ip(net, switch_name, svi_name, expected_cidr):
    h = sp_node(net, switch_name)
    if h is None:
        return False
    out = h.cmd(f'ip addr show {svi_name}').replace('\r', '')
    label = f'{svi_name} tiene {expected_cidr}'
    if re.search(re.escape(expected_cidr), out):
        ok(label)
        return True
    fail(label, out)
    return False


def sp_dhclient_renew(net, host_name, intf, expected_prefix, expected_cidr, gateway):
    h = sp_node(net, host_name)
    if h is None:
        return False

    h.cmd(f'dhclient -4 -r {intf} 2>/dev/null || true')
    h.cmd(f'ip addr flush dev {intf}')

    out = h.cmd(f'timeout 20 dhclient -4 -1 -v {intf} 2>&1')
    label = f'{host_name} obtuvo lease DHCP'

    if 'DHCPACK' not in out or 'bound to' not in out:
        fail(label, out)
        return False
    ok(label)

    # Verificar IP en rango
    ip_out = h.cmd(f'ip -4 addr show dev {intf}').replace('\r', '')
    match = re.search(r'inet\s+(\d+\.\d+\.\d+\.\d+)/(\d+)', ip_out)
    if not match:
        fail(f'{host_name} IP en rango {expected_prefix}x/{expected_cidr}', ip_out)
        return False

    assigned_ip   = match.group(1)
    assigned_cidr = int(match.group(2))

    if assigned_ip.startswith(expected_prefix) and assigned_cidr == expected_cidr:
        ok(f'{host_name} IP {assigned_ip}/{assigned_cidr} en rango correcto')
    else:
        fail(f'{host_name} IP esperada {expected_prefix}x/{expected_cidr}',
             f'IP actual: {assigned_ip}/{assigned_cidr}')
        return False

    # Verificar default gateway
    route_out = h.cmd('ip route').replace('\r', '')
    if f'default via {gateway}' in route_out:
        ok(f'{host_name} default gateway {gateway}')
        return True

    fail(f'{host_name} default gateway {gateway}', route_out)
    return False


def sp_get_ipv4(net, host_name, intf):
    h = sp_node(net, host_name)
    if h is None:
        return None
    out = h.cmd(f'ip -4 addr show dev {intf}').replace('\r', '')
    match = re.search(r'inet\s+(\d+\.\d+\.\d+\.\d+)/\d+', out)
    return match.group(1) if match else None


# ── validacion principal ──────────────────────────────────────────────────────

def run_validation_sp(net):
    total = 0
    passed = 0

    def test(result):
        nonlocal total, passed
        total += 1
        if result:
            passed += 1

    print(f'\n{BOLD}{CYAN}######################################################{RESET}')
    print(f'{BOLD}{CYAN}#   VALIDACION - TIENDA SAN PEDRO                    #{RESET}')
    print(f'{BOLD}{CYAN}######################################################{RESET}')

    # ── 1. Procesos activos ───────────────────────────────────────────────────
    section('1. Procesos DHCP')
    test(sp_process_running(net, 'dhcp_sp', 'dnsmasq',  'dnsmasq activo en dhcp_sp'))
    test(sp_process_running(net, 's17',     'dhcrelay', 'dhcrelay activo en s17 (core L3)'))

    # ── 2. SVIs del core L3 ───────────────────────────────────────────────────
    section('2. SVIs en s17 (core L3)')
    test(sp_svi_has_ip(net, 's17', 'sp_vlan130', '10.3.0.1/24'))
    test(sp_svi_has_ip(net, 's17', 'sp_vlan140', '10.3.1.1/27'))
    test(sp_svi_has_ip(net, 's17', 'sp_vlan40',  '10.3.1.33/29'))
    test(sp_svi_has_ip(net, 's17', 'sp_vlan30',  '10.3.1.41/29'))
    test(sp_svi_has_ip(net, 's17', 'sp_vlan100', '10.3.1.49/25'))
    test(sp_svi_has_ip(net, 's17', 'sp_vlan110', '10.3.1.113/28'))
    test(sp_svi_has_ip(net, 's17', 'sp_vlan120', '10.3.1.129/29'))
    test(sp_svi_has_ip(net, 's17', 'sp_vlan998', '192.168.105.254/24'))
    test(sp_svi_has_ip(net, 's17', 'sp_vlan999', '10.3.255.253/30'))

    # ── 3. Conectividad servidor DHCP ─────────────────────────────────────────
    section('3. Conectividad servidor DHCP')
    test(sp_ping(net, 'dhcp_sp', '192.168.105.254', 'dhcp_sp -> s17 (VLAN 998)'))
    test(sp_ping(net, 's17',     '192.168.105.10',  's17 -> dhcp_sp'))

    # ── 4. DHCP leases por VLAN ───────────────────────────────────────────────
    section('4. DHCP leases por VLAN')
    for host, vlan, gateway, label, prefix, cidr in SP_VLAN_HOSTS:
        test(sp_dhclient_renew(net, host, f'{host}-eth0', prefix, cidr, gateway))

    # ── 5. Host -> gateway ────────────────────────────────────────────────────
    section('5. Host -> gateway (SVI en s16)')
    for host, vlan, gateway, label, _, _ in SP_VLAN_HOSTS:
        test(sp_ping(net, host, gateway,
                     f'{host} -> {gateway}  [VLAN {vlan} {label}]'))

    # ── 6. Routing inter-VLAN ─────────────────────────────────────────────────
    section('6. Routing inter-VLAN')
    host_ips = {}
    for host, _, _, _, _, _ in SP_VLAN_HOSTS:
        ip = sp_get_ipv4(net, host, f'{host}-eth0')
        if ip:
            host_ips[host] = ip
        else:
            fail(f'No se pudo obtener IP de {host}')

    pairs_tested = set()
    for src, src_vlan, _, src_label, _, _ in SP_VLAN_HOSTS:
        for dst, dst_vlan, _, dst_label, _, _ in SP_VLAN_HOSTS:
            if src == dst or (dst, src) in pairs_tested:
                continue
            pairs_tested.add((src, dst))
            if src in host_ips and dst in host_ips:
                test(sp_ping(net, src, host_ips[dst],
                             f'{src} [VLAN {src_vlan}] -> {dst} ({host_ips[dst]}) [VLAN {dst_vlan}]'))
            else:
                fail(f'{src} -> {dst}: IPs no disponibles')
                test(False)

    # ── 7. Transit link s17 <-> sp_r ─────────────────────────────────────────
    section('7. Transit link (s17 core L3 <-> sp_r)')
    test(sp_ping(net, 's17',  '10.3.255.254', 's17  -> sp_r (10.3.255.254)'))
    test(sp_ping(net, 'sp_r', '10.3.255.253', 'sp_r -> s17  (10.3.255.253)'))

    # ── Resultado ─────────────────────────────────────────────────────────────
    print(f'\n{BOLD}Resultado: {passed}/{total} pruebas exitosas{RESET}')
    if passed == total:
        print(f'{GREEN}{BOLD}TODO OK: Tienda San Pedro funcionando correctamente.{RESET}\n')
        return True
    print(f'{RED}{BOLD}HAY FALLAS: revisa los [FAIL] de arriba.{RESET}\n')
    return False


# ── entry point ───────────────────────────────────────────────────────────────

def run():
    net = Mininet(
        controller=None,
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True,
        autoStaticArp=False
    )

    sp = TiendaSanPedro()
    sp.build(net)

    net.start()
    sp.configure()

    run_validation_sp(net)

    CLI(net)

    sp.stop_services()
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    run()
