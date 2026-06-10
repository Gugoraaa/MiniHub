from mininet.net import Mininet
from mininet.node import OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel

from sites.tiendaSanPedro import TiendaSanPedro

BOLD  = '\033[1m'
CYAN  = '\033[96m'
GREEN = '\033[92m'
RED   = '\033[91m'
RESET = '\033[0m'

SP_HOSTS = [
    ('sp_hwifi',  '10.3.0.',  130, 'WiFi'),
    ('sp_hchk',   '10.3.1.',  140, 'Checkout'),
    ('sp_hadmin', '10.3.1.',   40, 'Admin'),
    ('sp_hsec',   '10.3.1.',   30, 'Security'),
    ('sp_hcam',   '10.3.1.', 100, 'Camaras'),
    ('sp_hprint', '10.3.1.', 110, 'Impresoras'),
    ('sp_hphone', '10.3.1.', 120, 'Telefonos'),
]


def dhcp_all(net):
    """Pide lease DHCP a todos los hosts."""
    print(f'\n{BOLD}{CYAN}=== DHCP: solicitando IPs ==={RESET}')

    for host_name, prefix, vlan, label in SP_HOSTS:
        h = net.get(host_name)
        h.cmd(f'dhclient -4 -r {host_name}-eth0 2>/dev/null || true')
        h.cmd(f'ip addr flush dev {host_name}-eth0')
        out = h.cmd(f'timeout 20 dhclient -4 -1 {host_name}-eth0 2>&1')

        ip_line = h.cmd(f'ip -4 addr show dev {host_name}-eth0 | grep inet').strip().replace('\r', '')

        if 'bound to' in out and ip_line:
            ip = ip_line.split()[1]
            print(f'{GREEN}[OK]{RESET}   {host_name:12} VLAN {vlan:3} {label:12} → {ip}')
        else:
            print(f'{RED}[FAIL]{RESET} {host_name:12} VLAN {vlan:3} {label:12} → sin lease')


def ping_between_vlans(net):
    """Ping de cada host a todos los demás para verificar routing inter-VLAN."""
    print(f'\n{BOLD}{CYAN}=== Ping inter-VLAN ==={RESET}')

    host_ips = {}
    for host_name, _, _, _ in SP_HOSTS:
        h = net.get(host_name)
        out = h.cmd(f'ip -4 addr show dev {host_name}-eth0 | grep inet').strip().replace('\r', '')
        if out:
            host_ips[host_name] = out.split()[1].split('/')[0]

    total = passed = 0
    for src_name, _, src_vlan, src_label in SP_HOSTS:
        for dst_name, _, dst_vlan, dst_label in SP_HOSTS:
            if src_name == dst_name:
                continue
            if src_name not in host_ips or dst_name not in host_ips:
                continue

            dst_ip = host_ips[dst_name]
            out = net.get(src_name).cmd(f'ping -c 2 -W 1 {dst_ip}')
            total += 1

            if '0% packet loss' in out:
                passed += 1
                print(f'{GREEN}[OK]{RESET}   {src_name} (VLAN {src_vlan}) -> {dst_name} (VLAN {dst_vlan}) [{dst_ip}]')
            else:
                print(f'{RED}[FAIL]{RESET} {src_name} (VLAN {src_vlan}) -> {dst_name} (VLAN {dst_vlan}) [{dst_ip}]')

    print(f'\n{BOLD}Resultado inter-VLAN: {passed}/{total}{RESET}')
    if passed == total:
        print(f'{GREEN}{BOLD}Todo OK — routing inter-VLAN funcionando.{RESET}')
    else:
        print(f'{RED}{BOLD}Hay fallas de conectividad entre VLANs.{RESET}')


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

    # 1. Pedir IPs por DHCP
    dhcp_all(net)

    # 2. Ping entre todas las VLANs
    ping_between_vlans(net)

    # 3. CLI para pruebas manuales
    CLI(net)

    sp.stop_services()
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    run()
