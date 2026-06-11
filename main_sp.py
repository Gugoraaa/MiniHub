from mininet.net import Mininet
from mininet.node import OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel

from sites.tiendaSanPedro import TiendaSanPedro
from validate_network import (
    section, ok, fail,
    ping_test, dhcp_renew, process_running, get_ipv4, interface_has_ip,
    BOLD, CYAN, GREEN, RED, RESET,
)

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


def run_validation_sp(net):
    total = 0
    passed = 0

    def test(result):
        nonlocal total, passed
        total += 1
        if result:
            passed += 1

    print(f"\n{BOLD}{CYAN}######################################################{RESET}")
    print(f"{BOLD}{CYAN}#   VALIDACION AUTOMATICA - TIENDA SAN PEDRO         #{RESET}")
    print(f"{BOLD}{CYAN}######################################################{RESET}")

    # =========================================================
    # 1. Procesos DHCP
    # =========================================================
    section("1. Procesos DHCP")

    test(process_running(net, 'dhcp_sp', 'dnsmasq', 'dnsmasq activo en dhcp_sp'))
    test(process_running(net, 's16', 'dhcrelay', 'dhcrelay activo en s16 (MLS)'))

    # =========================================================
    # 2. Interfaces de transito y DHCP
    # =========================================================
    section("2. Interfaces de transito")

    test(interface_has_ip(net, 'dhcp_sp', 'dhcp_sp-eth0', '192.168.105.10/24'))
    test(interface_has_ip(net, 's16', 'sp_vlan998', '192.168.105.254/24'))
    test(interface_has_ip(net, 's16', 'sp_vlan999', '10.3.255.253/30'))
    test(interface_has_ip(net, 'sp_r', 'sp_r-eth0', '10.3.255.254/30'))

    # =========================================================
    # 3. Conectividad servidor DHCP
    # =========================================================
    section("3. Conectividad servidor DHCP")

    test(ping_test(net, 'dhcp_sp', '192.168.105.254',
                   'dhcp_sp -> gateway VLAN 998 (s16)'))
    test(ping_test(net, 's16', '192.168.105.10',
                   's16 -> dhcp_sp'))

    # =========================================================
    # 4. DHCP leases por VLAN
    # =========================================================
    section("4. DHCP leases por VLAN")

    for host, vlan, gateway, label, prefix, cidr in SP_VLAN_HOSTS:
        test(dhcp_renew(
            net, host, f'{host}-eth0', prefix, cidr, gateway,
        ))

    # =========================================================
    # 5. Host -> gateway SVI en s16
    # =========================================================
    section("5. Host -> gateway (SVI en s16)")

    for host, vlan, gateway, label, _, _ in SP_VLAN_HOSTS:
        test(ping_test(
            net, host, gateway,
            f'{host} -> {gateway}  [VLAN {vlan} / {label}]',
        ))

    # =========================================================
    # 6. Routing inter-VLAN
    # =========================================================
    section("6. Routing inter-VLAN")

    host_ips = {}
    for host, _, _, _, _, _ in SP_VLAN_HOSTS:
        ip = get_ipv4(net, host, f'{host}-eth0')
        if ip:
            host_ips[host] = ip.split('/')[0]
        else:
            fail(f'No se pudo obtener IP de {host}')

    for src_host, src_vlan, _, src_label, _, _ in SP_VLAN_HOSTS:
        for dst_host, dst_vlan, _, dst_label, _, _ in SP_VLAN_HOSTS:
            if src_host == dst_host:
                continue
            if src_host in host_ips and dst_host in host_ips:
                dst_ip = host_ips[dst_host]
                test(ping_test(
                    net, src_host, dst_ip,
                    f'{src_host} (VLAN {src_vlan} {src_label}) -> '
                    f'{dst_host} ({dst_ip}) [VLAN {dst_vlan} {dst_label}]',
                ))
            else:
                fail(f'{src_host} -> {dst_host}: IPs no disponibles')
                test(False)

    # =========================================================
    # 7. Router San Pedro
    # =========================================================
    section("7. Router San Pedro (sp_r)")

    test(ping_test(net, 'sp_r', '10.3.255.253',
                   'sp_r -> s16 (transito 10.3.255.253)'))
    test(ping_test(net, 's16', '10.3.255.254',
                   's16 -> sp_r (transito 10.3.255.254)'))

    # =========================================================
    # Resultado final
    # =========================================================
    print(f"\n{BOLD}Resultado: {passed}/{total} pruebas exitosas{RESET}")

    if passed == total:
        print(f"{GREEN}{BOLD}TODO SUCCESS: Tienda San Pedro funcionando correctamente.{RESET}\n")
        return True

    print(f"{RED}{BOLD}HAY FALLAS: revisa las pruebas marcadas como FAIL arriba.{RESET}\n")
    return False


def run():
    net = Mininet(
        controller=None,
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True,
        autoStaticArp=False
    )

    # =========================
    # Crear y construir sede
    # =========================
    sp = TiendaSanPedro()
    sp.build(net)

    # =========================
    # Iniciar red
    # =========================
    net.start()

    # =========================
    # Configurar sede
    # =========================
    sp.configure()

    # =========================
    # Pruebas automaticas
    # =========================
    run_validation_sp(net)

    # =========================
    # CLI Mininet
    # =========================
    CLI(net)

    # =========================
    # Limpieza
    # =========================
    sp.stop_services()
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    run()
