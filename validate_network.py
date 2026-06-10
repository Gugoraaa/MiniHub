# validate_network.py
# Pruebas automáticas para topología Mininet HQ + Warehouse
# Uso dentro del CLI de Mininet:
#   mininet> py exec(open("validate_network.py").read()); run_validation(net)
#
# O en main.py:
#   from validate_network import run_validation
#   run_validation(net)

import re
import time


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

    # Limpia cliente anterior y dirección anterior para evitar "Address already assigned"
    cmd(h, f"killall dhclient 2>/dev/null || true")
    cmd(h, f"dhclient -r {intf} 2>/dev/null || true")
    cmd(h, f"ip addr flush dev {intf}")

    out = cmd(h, f"timeout 25 dhclient -v {intf} 2>&1")

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

    print(f"\n{BOLD}{CYAN}############################################{RESET}")
    print(f"{BOLD}{CYAN}# VALIDACIÓN AUTOMÁTICA HQ + WAREHOUSE      #{RESET}")
    print(f"{BOLD}{CYAN}############################################{RESET}")

    section("1. Procesos DHCP")
    test(process_running(net, "dhcp_wh", "dnsmasq", "dnsmasq activo en dhcp_wh"))
    test(process_running(net, "s8", "dhcrelay", "dhcrelay activo en s8 / MLS Warehouse"))

    section("2. Interfaces WAN / tránsito")
    test(interface_has_ip(net, "r_wh", "r_wh-eth0", "10.4.1.254/30"))
    test(interface_has_ip(net, "hqr", "hqr-eth1", "10.0.3.1/30"))
    test(interface_has_ip(net, "r_wh", "r_wh-eth1", "10.0.3.2/30"))

    # DHCP de Warehouse
    test(dhcp_renew(net, "ic1", "ic1-eth0", "10.4.0.", 27, "10.4.0.1"))
    test(dhcp_renew(net, "office1", "office1-eth0", "10.4.0.", 27, "10.4.0.33"))

    section("3. Gateways Warehouse")
    test(ping_test(net, "ic1", "10.4.0.1", "ic1 llega a gateway VLAN 70"))
    test(ping_test(net, "office1", "10.4.0.33", "office1 llega a gateway VLAN 40"))
    test(ping_test(net, "ic1", "10.4.1.254", "ic1 llega al router Warehouse"))

    section("4. Routing inter-VLAN Warehouse")
    # Se obtiene la IP real de office1 para no hardcodear lease
    office_ip = get_ipv4(net, "office1", "office1-eth0")
    ic1_ip = get_ipv4(net, "ic1", "ic1-eth0")

    if office_ip:
        office_addr = office_ip.split("/")[0]
        test(ping_test(net, "ic1", office_addr, f"ic1 llega a office1 ({office_addr})"))
    else:
        test(False)

    if ic1_ip:
        ic1_addr = ic1_ip.split("/")[0]
        test(ping_test(net, "office1", ic1_addr, f"office1 llega a ic1 ({ic1_addr})"))
    else:
        test(False)

    section("5. WAN HQ <-> Warehouse")
    test(ping_test(net, "r_wh", "10.0.3.1", "r_wh llega a hqr por WAN"))
    test(ping_test(net, "hqr", "10.0.3.2", "hqr llega a r_wh por WAN"))

    section("6. HQ local")
    test(ping_test(net, "hit", "10.1.0.1", "hit llega a su gateway HQ"))

    section("7. Comunicación entre sedes")
    test(ping_test(net, "ic1", "10.1.0.2", "Warehouse ic1 llega a HQ hit"))
    if ic1_ip:
        ic1_addr = ic1_ip.split("/")[0]
        test(ping_test(net, "hit", ic1_addr, f"HQ hit llega a Warehouse ic1 ({ic1_addr})"))
    else:
        test(False)

    print(f"\n{BOLD}Resultado final: {passed}/{total} pruebas exitosas{RESET}")

    if passed == total:
        print(f"{GREEN}{BOLD}TODO SUCCESS: La topología HQ + Warehouse está funcionando correctamente.{RESET}\n")
        return True

    print(f"{RED}{BOLD}HAY FALLAS: revisa las pruebas marcadas como FAIL arriba.{RESET}\n")
    return False
