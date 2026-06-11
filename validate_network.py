# validate_network.py
# Pruebas automáticas para topología Mininet HQ + Warehouse + Tienda 2
#
# Uso recomendado en main.py:
#   from validate_network import run_validation
#   run_validation(net)

import re


GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def ok(label):
    print(f"{GREEN}[SUCCESS]{RESET} {label}")


def fail(label, details=""):
    print(f"{RED}[FAIL]{RESET} {label}")
    if details:
        print(f"{RED}{details.strip()}{RESET}")


def warn(label, details=""):
    print(f"{YELLOW}[WARN]{RESET} {label}")
    if details:
        print(f"{YELLOW}{details.strip()}{RESET}")


def section(title):
    print(f"\n{BOLD}{CYAN}=== {title} ==={RESET}")


def node(net, name):
    try:
        return net.get(name)
    except Exception as e:
        fail(f"Nodo {name} existe", str(e))
        return None


def cmd(n, command):
    return n.cmd(command)


def ping_test(net, src_name, dst, label=None, count=3):
    src = node(net, src_name)
    if src is None:
        return False

    label = label or f"{src_name} -> {dst}"
    out = cmd(src, f"ping -c {count} -W 1 {dst}")

    if " 0% packet loss" in out or ", 0% packet loss" in out:
        ok(label)
        return True

    fail(label, out)
    return False


def route_has_default(net, host_name, gateway):
    h = node(net, host_name)
    if h is None:
        return False

    out = cmd(h, "ip route")
    expected = f"default via {gateway}"

    if expected in out:
        ok(f"{host_name} tiene default gateway {gateway}")
        return True

    fail(f"{host_name} tiene default gateway {gateway}", out)
    return False


def get_ipv4(net, host_name, intf):
    h = node(net, host_name)
    if h is None:
        return None

    out = cmd(h, f"ip -4 addr show dev {intf}")
    match = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)/(\d+)", out)

    if match:
        return f"{match.group(1)}/{match.group(2)}"

    return None


def ip_starts_with(net, host_name, intf, prefix, cidr, label=None):
    ip = get_ipv4(net, host_name, intf)
    label = label or f"{host_name} recibió IP {prefix}x/{cidr}"

    if ip and ip.startswith(prefix) and ip.endswith(f"/{cidr}"):
        ok(f"{label}: {ip}")
        return True

    fail(label, f"IP actual: {ip}")
    return False


def dhcp_renew(net, host_name, intf, expected_prefix, expected_cidr, gateway):
    h = node(net, host_name)
    if h is None:
        return False

    section(f"DHCP en {host_name}")

    pid_path = f"tmp/dhclient-{host_name}.pid"
    lease_path = f"tmp/dhclient-{host_name}.leases"

    cmd(h, f"touch {lease_path}")
    cmd(h, f"test ! -f {pid_path} || kill $(cat {pid_path}) 2>/dev/null || true")
    cmd(h, f"dhclient -4 -r -pf {pid_path} -lf {lease_path} {intf} 2>/dev/null || true")
    cmd(h, f"ip addr flush dev {intf}")

    out = cmd(h, f"timeout 25 dhclient -4 -1 -v -pf {pid_path} -lf {lease_path} {intf} 2>&1")

    if "DHCPACK" in out and "bound to" in out:
        ok(f"{host_name} obtuvo lease DHCP")
    else:
        fail(f"{host_name} obtuvo lease DHCP", out)
        return False

    ip_ok = ip_starts_with(
        net,
        host_name,
        intf,
        expected_prefix,
        expected_cidr,
        f"{host_name} IP esperada"
    )

    route_ok = route_has_default(net, host_name, gateway)

    return ip_ok and route_ok


def process_running(net, host_name, pattern, label):
    h = node(net, host_name)
    if h is None:
        return False

    out = cmd(h, f"ps aux | grep '{pattern}' | grep -v grep")

    if out.strip():
        ok(label)
        return True

    fail(label, f"No se encontró proceso: {pattern}")
    return False


def interface_has_ip(net, host_name, intf, expected_ip_cidr):
    h = node(net, host_name)
    if h is None:
        return False

    out = cmd(h, f"ip -4 addr show dev {intf}")

    if expected_ip_cidr in out:
        ok(f"{host_name}:{intf} tiene {expected_ip_cidr}")
        return True

    fail(f"{host_name}:{intf} tiene {expected_ip_cidr}", out)
    return False


def run_validation(net):
    total = 0
    passed = 0

    def test(result):
        nonlocal total, passed
        total += 1
        if result:
            passed += 1

    print(f"\n{BOLD}{CYAN}######################################################{RESET}")
    print(f"{BOLD}{CYAN}# VALIDACIÓN AUTOMÁTICA HQ + WAREHOUSE + TIENDAS      #{RESET}")
    print(f"{BOLD}{CYAN}######################################################{RESET}")

    # =========================================================
    # 1. Procesos DHCP
    # =========================================================
    section("1. Procesos DHCP")

    test(process_running(net, "dhcp_wh", "dnsmasq", "dnsmasq activo en dhcp_wh"))
    test(process_running(net, "s8", "dhcrelay", "dhcrelay activo en s8 / MLS Warehouse"))

    test(process_running(net, "dhcp_t2", "dnsmasq", "dnsmasq activo en dhcp_t2"))
    test(process_running(net, "s12", "dhcrelay", "dhcrelay activo en s12 / MLS Tienda 2"))

    test(process_running(net, "dhcp_sp", "dnsmasq",  "dnsmasq activo en dhcp_sp"))
    test(process_running(net, "s17",     "dhcrelay", "dhcrelay activo en s17 / core L3 San Pedro"))

    # =========================================================
    # 2. Interfaces WAN / tránsito
    # =========================================================
    section("2. Interfaces WAN / tránsito")

    # Warehouse interno
    test(interface_has_ip(net, "r_wh", "r_wh-eth0", "10.4.1.254/30"))

    # HQ <-> Warehouse
    test(interface_has_ip(net, "hqr", "hqr-eth1", "10.0.3.1/30"))
    test(interface_has_ip(net, "r_wh", "r_wh-eth1", "10.0.3.2/30"))

    # Tienda 2 interno
    test(interface_has_ip(net, "r_t2", "r_t2-wan", "10.3.1.250/30"))

    # HQ <-> Tienda 2
    test(interface_has_ip(net, "hqr", "hqr-eth2", "10.0.4.1/30"))
    test(interface_has_ip(net, "r_t2", "r_t2-eth1", "10.0.4.2/30"))

    # San Pedro interno
    test(interface_has_ip(net, "sp_r", "sp_r-eth0", "10.2.255.254/30"))

    # HQ <-> San Pedro
    test(interface_has_ip(net, "hqr",  "hqr-eth3",  "10.0.5.1/30"))
    test(interface_has_ip(net, "sp_r", "sp_r-eth1",  "10.0.5.2/30"))

    # =========================================================
    # 3. DHCP Warehouse
    # =========================================================
    test(dhcp_renew(net, "ic1", "ic1-eth0", "10.4.0.", 27, "10.4.0.1"))
    test(dhcp_renew(net, "office1", "office1-eth0", "10.4.0.", 27, "10.4.0.33"))

    # =========================================================
    # 4. DHCP Tienda 2
    # =========================================================
    test(dhcp_renew(net, "checkout", "checkout-eth0", "10.3.1.", 27, "10.3.1.1"))
    test(dhcp_renew(net, "pc_admin", "pc_admin-eth0", "10.3.1.", 28, "10.3.1.33"))

    # =========================================================
    # 4b. DHCP Tienda San Pedro
    # =========================================================
    test(dhcp_renew(net, "sp_hchk",  "sp_hchk-eth0",  "10.2.1.", 27, "10.2.1.1"))
    test(dhcp_renew(net, "sp_hwifi", "sp_hwifi-eth0", "10.2.0.", 24, "10.2.0.1"))

    # =========================================================
    # 5. Gateways Warehouse
    # =========================================================
    section("5. Gateways Warehouse")

    test(ping_test(net, "ic1", "10.4.0.1", "ic1 llega a gateway VLAN 70"))
    test(ping_test(net, "office1", "10.4.0.33", "office1 llega a gateway VLAN 40"))
    test(ping_test(net, "ic1", "10.4.1.254", "ic1 llega al router Warehouse"))

    # =========================================================
    # 6. Gateways Tienda 2
    # =========================================================
    section("6. Gateways Tienda 2")

    test(ping_test(net, "checkout", "10.3.1.1", "checkout llega a gateway VLAN 140"))
    test(ping_test(net, "pc_admin", "10.3.1.33", "pc_admin llega a gateway VLAN 40"))
    

    # =========================================================
    # 7. Routing inter-VLAN Warehouse
    # =========================================================
    section("7. Routing inter-VLAN Warehouse")

    office_ip = get_ipv4(net, "office1", "office1-eth0")
    ic1_ip = get_ipv4(net, "ic1", "ic1-eth0")

    if office_ip:
        office_addr = office_ip.split("/")[0]
        test(ping_test(net, "ic1", office_addr, f"ic1 llega a office1 ({office_addr})"))
    else:
        fail("No se pudo obtener IP de office1")
        test(False)

    if ic1_ip:
        ic1_addr = ic1_ip.split("/")[0]
        test(ping_test(net, "office1", ic1_addr, f"office1 llega a ic1 ({ic1_addr})"))
    else:
        fail("No se pudo obtener IP de ic1")
        test(False)

    # =========================================================
    # 8. Routing inter-VLAN Tienda 2
    # =========================================================
    section("8. Routing inter-VLAN Tienda 2")

    checkout_ip = get_ipv4(net, "checkout", "checkout-eth0")
    pc_admin_ip = get_ipv4(net, "pc_admin", "pc_admin-eth0")

    if checkout_ip:
        checkout_addr = checkout_ip.split("/")[0]
        test(ping_test(net, "pc_admin", checkout_addr, f"pc_admin llega a checkout ({checkout_addr})"))
    else:
        fail("No se pudo obtener IP de checkout")
        test(False)

    if pc_admin_ip:
        pc_admin_addr = pc_admin_ip.split("/")[0]
        test(ping_test(net, "checkout", pc_admin_addr, f"checkout llega a pc_admin ({pc_admin_addr})"))
    else:
        fail("No se pudo obtener IP de pc_admin")
        test(False)

    # =========================================================
    # 7b. Gateways Tienda San Pedro
    # =========================================================
    section("7b. Gateways Tienda San Pedro")

    test(ping_test(net, "sp_hchk",  "10.2.1.1",     "sp_hchk  llega a gateway VLAN 140"))
    test(ping_test(net, "sp_hwifi", "10.2.0.1",     "sp_hwifi llega a gateway VLAN 130"))
    test(ping_test(net, "sp_hchk",  "10.2.255.253", "sp_hchk llega al core L3 San Pedro"))

    # =========================================================
    # 8b. Routing inter-VLAN Tienda San Pedro
    # =========================================================
    section("8b. Routing inter-VLAN Tienda San Pedro")

    sp_hchk_ip  = get_ipv4(net, "sp_hchk",  "sp_hchk-eth0")
    sp_hwifi_ip = get_ipv4(net, "sp_hwifi", "sp_hwifi-eth0")

    if sp_hwifi_ip:
        sp_hwifi_addr = sp_hwifi_ip.split("/")[0]
        test(ping_test(net, "sp_hchk", sp_hwifi_addr,
                       f"sp_hchk (VLAN 140) llega a sp_hwifi ({sp_hwifi_addr}) (VLAN 130)"))
    else:
        fail("No se pudo obtener IP de sp_hwifi")
        test(False)

    if sp_hchk_ip:
        sp_hchk_addr = sp_hchk_ip.split("/")[0]
        test(ping_test(net, "sp_hwifi", sp_hchk_addr,
                       f"sp_hwifi (VLAN 130) llega a sp_hchk ({sp_hchk_addr}) (VLAN 140)"))
    else:
        fail("No se pudo obtener IP de sp_hchk")
        test(False)

    # =========================================================
    # 9. WAN HQ <-> Warehouse
    # =========================================================
    section("9. WAN HQ <-> Warehouse")

    test(ping_test(net, "r_wh", "10.0.3.1", "r_wh llega a hqr por WAN"))
    test(ping_test(net, "hqr", "10.0.3.2", "hqr llega a r_wh por WAN"))

    # =========================================================
    # 10. WAN HQ <-> Tienda 2
    # =========================================================
    section("10. WAN HQ <-> Tienda 2")

    test(ping_test(net, "r_t2", "10.0.4.1", "r_t2 llega a hqr por WAN"))
    test(ping_test(net, "hqr", "10.0.4.2", "hqr llega a r_t2 por WAN"))

    # =========================================================
    # 10b. WAN HQ <-> Tienda San Pedro
    # =========================================================
    section("10b. WAN HQ <-> Tienda San Pedro")

    test(ping_test(net, "sp_r", "10.0.5.1", "sp_r llega a hqr por WAN"))
    test(ping_test(net, "hqr",  "10.0.5.2", "hqr llega a sp_r por WAN"))

    # =========================================================
    # 11. HQ local
    # =========================================================
    section("11. HQ local")

    test(ping_test(net, "hsales", "10.1.0.33", "hsales llega a su gateway HQ"))

    # =========================================================
    # 12. Comunicación Warehouse <-> HQ
    # =========================================================
    section("12. Comunicación Warehouse <-> HQ")

    test(ping_test(net, "ic1", "10.1.0.34", "Warehouse ic1 llega a HQ hsales"))

    if ic1_ip:
        ic1_addr = ic1_ip.split("/")[0]
        test(ping_test(net, "hsales", ic1_addr, f"HQ hsales llega a Warehouse ic1 ({ic1_addr})"))
    else:
        fail("No se pudo obtener IP de ic1")
        test(False)

    # =========================================================
    # 13. Comunicación Tienda 2 <-> HQ
    # =========================================================
    section("13. Comunicación Tienda 2 <-> HQ")

    test(ping_test(net, "checkout", "10.1.0.34", "Tienda 2 checkout llega a HQ hsales"))

    if checkout_ip:
        checkout_addr = checkout_ip.split("/")[0]
        test(ping_test(net, "hsales", checkout_addr, f"HQ hsales llega a Tienda 2 checkout ({checkout_addr})"))
    else:
        fail("No se pudo obtener IP de checkout")
        test(False)

    # =========================================================
    # 13b. Comunicación Tienda San Pedro <-> HQ
    # =========================================================
    section("13b. Comunicación Tienda San Pedro <-> HQ")

    test(ping_test(net, "sp_hchk", "10.1.0.34", "San Pedro sp_hchk llega a HQ hsales"))

    if sp_hchk_ip:
        sp_hchk_addr = sp_hchk_ip.split("/")[0]
        test(ping_test(net, "hsales", sp_hchk_addr,
                       f"HQ hsales llega a San Pedro sp_hchk ({sp_hchk_addr})"))
    else:
        fail("No se pudo obtener IP de sp_hchk")
        test(False)

    # =========================================================
    # Resultado final
    # =========================================================
    print(f"\n{BOLD}Resultado final: {passed}/{total} pruebas exitosas{RESET}")

    if passed == total:
        print(f"{GREEN}{BOLD}TODO SUCCESS: HQ + Warehouse + Tienda 2 + Tienda San Pedro funcionando correctamente.{RESET}\n")
        return True

    print(f"{RED}{BOLD}HAY FALLAS: revisa las pruebas marcadas como FAIL arriba.{RESET}\n")
    return False
