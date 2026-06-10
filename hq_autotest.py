#!/usr/bin/env python3

import os
import re
import subprocess
import sys
import time

from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.node import OVSSwitch

from sites.hq import HQSite


GREEN = "\033[92m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

BASEDIR = os.path.dirname(os.path.abspath(__file__))


def ok(label):
    print(f"{GREEN}[SUCCESS]{RESET} {label}")


def fail(label, details=""):
    print(f"{RED}[FAIL]{RESET} {label}")
    if details:
        print(f"{RED}{details.strip()}{RESET}")


def section(title):
    print(f"\n{BOLD}{CYAN}=== {title} ==={RESET}")


def runclean():
    subprocess.run(['bash', os.path.join(BASEDIR, 'clean.sh')], check=False)


def node(net, name):
    try:
        return net.get(name)
    except Exception as error:
        fail(f"Nodo {name} existe", str(error))
        return None


def cmd(n, command):
    return n.cmd(command)


def packet_loss_ok(output):
    return " 0% packet loss" in output or ", 0% packet loss" in output


def ping_test(net, src_name, dst, label=None, count=3):
    src = node(net, src_name)
    if src is None:
        return False

    label = label or f"{src_name} -> {dst}"
    out = cmd(src, f"ping -c {count} -W 1 {dst}")

    if packet_loss_ok(out):
        ok(label)
        return True

    fail(label, out)
    return False


def process_running(net, host_name, pattern, label):
    h = node(net, host_name)
    if h is None:
        return False

    out = cmd(h, f"ps aux | grep '{pattern}' | grep -v grep")

    if out.strip():
        ok(label)
        return True

    fail(label, f"No se encontro proceso: {pattern}")
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


def port_has_tag(net, switch_name, port, tag):
    sw = node(net, switch_name)
    if sw is None:
        return False

    out = cmd(sw, f"ovs-vsctl get port {port} tag").strip()

    if out == str(tag):
        ok(f"{switch_name}:{port} esta en VLAN {tag}")
        return True

    fail(f"{switch_name}:{port} esta en VLAN {tag}", out)
    return False


def extract_ipv4(output):
    match = re.search(r"(\d{1,3}(?:\.\d{1,3}){3})/(\d{1,2})", output)
    if not match:
        return None, None

    return match.group(1), int(match.group(2))


def extract_dhcp_bound_ip(output):
    match = re.search(r"bound to\s+(\d{1,3}(?:\.\d{1,3}){3})", output)
    if not match:
        return None

    return match.group(1)


def get_ipv4(net, host_name, intf):
    h = node(net, host_name)
    if h is None:
        return None

    out = cmd(h, f"ip -4 -o addr show dev {intf}")
    ip, prefix = extract_ipv4(out)

    if ip and prefix:
        return f"{ip}/{prefix}"

    return None


def route_has_default(net, host_name, gateway):
    h = node(net, host_name)
    if h is None:
        return False

    out = cmd(h, "ip route")
    normalized = " ".join(out.split())

    if f"default via {gateway}" in normalized:
        ok(f"{host_name} tiene default gateway {gateway}")
        return True

    fail(f"{host_name} tiene default gateway {gateway}", out)
    return False


def dhcp_renew_hq(net):
    h = node(net, "hdtest")
    if h is None:
        return False, None

    section("3. DHCP HQ")

    pid_path = "/tmp/dhclient-hdtest.pid"
    lease_path = "/tmp/dhclient-hdtest.leases"

    cmd(
        h,
        f"dhclient -r hdtest-eth0 2>/dev/null || true; "
        f"test ! -f {pid_path} || kill $(cat {pid_path}) 2>/dev/null || true; "
        f"killall dhclient 2>/dev/null || true; "
        f"ip addr flush dev hdtest-eth0; "
        f"ip link set hdtest-eth0 up; "
        f"rm -f {pid_path} {lease_path}; "
        f"touch {lease_path}"
    )

    out = cmd(
        h,
        f"timeout 35 dhclient -4 -1 -v "
        f"-pf {pid_path} -lf {lease_path} hdtest-eth0 2>&1"
    )

    if "DHCPACK" in out and "bound to" in out:
        ok("hdtest obtuvo lease DHCP")
    else:
        fail("hdtest obtuvo lease DHCP", out)
        return False, None

    assigned_ip = extract_dhcp_bound_ip(out)
    current_ip = get_ipv4(net, "hdtest", "hdtest-eth0")

    if current_ip is None and assigned_ip:
        current_ip = f"{assigned_ip}/27"

    if current_ip and current_ip.startswith("10.1.0.") and current_ip.endswith("/27"):
        ok(f"hdtest IP esperada: {current_ip}")
    else:
        fail("hdtest IP esperada", f"IP actual: {current_ip}")
        return False, assigned_ip

    route_ok = route_has_default(net, "hdtest", "10.1.0.1")

    return route_ok, assigned_ip


def dns_lookup_test(net, host_name, domain, expected_ip, server=None):
    h = node(net, host_name)
    if h is None:
        return False

    command = f"nslookup {domain}"
    label = f"{host_name} resuelve {domain}"

    if server:
        command = f"{command} {server}"
        label = f"{host_name} resuelve {domain} usando {server}"

    out = cmd(h, command)

    if f"Address: {expected_ip}" in out:
        ok(label)
        return True

    fail(label, out)
    return False


def http_test(net, host_name, url, expected_text):
    h = node(net, host_name)
    if h is None:
        return False

    out = cmd(h, f"curl --max-time 5 -s {url}")

    if expected_text in out:
        ok(f"{host_name} abre {url}")
        return True

    fail(f"{host_name} abre {url}", out)
    return False


def print_diagnostics(net):
    section("Diagnostico HQ")

    dhcphq = node(net, "dhcphq")
    s5 = node(net, "s5")
    hdtest = node(net, "hdtest")

    if dhcphq:
        print("dhcphq ps:")
        print(cmd(dhcphq, "ps aux | grep '[d]nsmasq'").strip())
        print("dhcp_hq.log:")
        print(cmd(dhcphq, "cat tmp/dhcp_hq.log 2>/dev/null").strip())

    if s5:
        print("s5 ps:")
        print(cmd(s5, "ps aux | grep '[d]hcrelay'").strip())

    if hdtest:
        print("hdtest interface:")
        print(cmd(hdtest, "ip addr show hdtest-eth0").strip())
        print("hdtest route:")
        print(cmd(hdtest, "ip route").strip())


def run_hq_validation(net):
    total = 0
    passed = 0

    def test(result):
        nonlocal total, passed
        total += 1
        if result:
            passed += 1

    print(f"\n{BOLD}{CYAN}######################################################{RESET}")
    print(f"{BOLD}{CYAN}# VALIDACION AUTOMATICA HQ                           #{RESET}")
    print(f"{BOLD}{CYAN}######################################################{RESET}")

    # =========================================================
    # 1. Procesos y servicios
    # =========================================================
    section("1. Procesos y servicios")

    test(process_running(net, "hdns", "dnsmasq.*hq/site.conf",
                         "dnsmasq DNS activo en hdns"))
    test(process_running(net, "hweb", "python3 -m http.server 80",
                         "HTTP server activo en hweb"))
    test(process_running(net, "dhcphq", "dnsmasq.*dhcp_hq.conf",
                         "dnsmasq DHCP activo en dhcphq"))
    test(process_running(net, "s5", "dhcrelay.*192.168.101.10",
                         "dhcrelay activo en s5 / MLS HQ"))

    # =========================================================
    # 2. Interfaces, VLANs y transito
    # =========================================================
    section("2. Interfaces, VLANs y transito")

    test(interface_has_ip(net, "s5", "hqvlan10", "10.1.0.1/27"))
    test(interface_has_ip(net, "s5", "hqdhcp", "192.168.101.254/24"))
    test(interface_has_ip(net, "s5", "hqwan", "10.1.2.1/30"))
    test(interface_has_ip(net, "hqr", "hqr-eth0", "10.1.2.2/30"))
    test(interface_has_ip(net, "hdns", "hdns-eth0", "10.1.0.10/27"))
    test(interface_has_ip(net, "hweb", "hweb-eth0", "10.1.0.11/27"))
    test(interface_has_ip(net, "dhcphq", "dhcphq-eth0", "192.168.101.10/24"))
    test(port_has_tag(net, "s1", "s1-eth4", 10))
    test(ping_test(net, "s5", "192.168.101.10",
                   "s5 llega al servidor DHCP 192.168.101.10"))

    # =========================================================
    # 3. DHCP HQ
    # =========================================================
    dhcp_ok, assigned_ip = dhcp_renew_hq(net)
    test(dhcp_ok)

    lease_text = ""
    dhcphq = node(net, "dhcphq")
    if dhcphq:
        lease_text = cmd(dhcphq, "cat tmp/dhcp_hq.leases 2>/dev/null")

    if assigned_ip and assigned_ip in lease_text:
        ok(f"lease DHCP registrada para hdtest ({assigned_ip})")
        test(True)
    else:
        fail("lease DHCP registrada para hdtest", lease_text)
        test(False)

    # =========================================================
    # 4. Gateways y conectividad local HQ
    # =========================================================
    section("4. Gateways y conectividad local HQ")

    test(ping_test(net, "hit", "10.1.0.1", "hit llega a gateway VLAN 10"))
    test(ping_test(net, "hdtest", "10.1.0.1", "hdtest llega a gateway VLAN 10"))
    test(ping_test(net, "hdtest", "10.1.0.10", "hdtest llega al DNS HQ"))

    if assigned_ip:
        test(ping_test(net, "hit", assigned_ip,
                       f"hit llega a hdtest por IP DHCP ({assigned_ip})"))
    else:
        fail("hit llega a hdtest por IP DHCP", "No se obtuvo IP DHCP")
        test(False)

    test(ping_test(net, "s5", "10.1.2.2", "s5 llega al router WAN hqr"))
    test(ping_test(net, "hqr", "10.1.2.1", "hqr llega al MLS s5"))

    # =========================================================
    # 5. DNS y HTTP HQ
    # =========================================================
    section("5. DNS y HTTP HQ")

    test(dns_lookup_test(net, "hit", "dns.hq.local", "10.1.0.10", "10.1.0.10"))
    test(dns_lookup_test(net, "hit", "web.hq.local", "10.1.0.11"))
    test(dns_lookup_test(net, "hdtest", "web.hq.local", "10.1.0.11", "10.1.0.10"))
    test(dns_lookup_test(net, "hdtest", "web.hq.local", "10.1.0.11"))
    test(http_test(net, "hit", "http://web.hq.local", "MiniHub HQ Web Server"))
    test(http_test(net, "hdtest", "http://web.hq.local", "MiniHub HQ Web Server"))

    # =========================================================
    # Resultado final
    # =========================================================
    print(f"\n{BOLD}Resultado final HQ: {passed}/{total} pruebas exitosas{RESET}")

    if passed == total:
        print(f"{GREEN}{BOLD}TODO SUCCESS: HQ esta funcionando correctamente.{RESET}\n")
        return True

    print(f"{RED}{BOLD}HAY FALLAS: revisa las pruebas marcadas como FAIL arriba.{RESET}\n")
    print_diagnostics(net)
    return False


def main():
    os.chdir(BASEDIR)
    runclean()

    net = Mininet(
        controller=None,
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True,
        autoStaticArp=False,
    )

    ok_result = False

    try:
        hq = HQSite()
        hq.build(net)

        net.start()
        hq.configure()
        time.sleep(2)

        ok_result = run_hq_validation(net)
    finally:
        net.stop()
        runclean()

    return 0 if ok_result else 1


if __name__ == "__main__":
    setLogLevel("info")
    sys.exit(main())
