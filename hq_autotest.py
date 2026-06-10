#!/usr/bin/env python3

import os
import re
import subprocess
import sys

from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.node import OVSSwitch

from sites.hq import HQSite


BASEDIR = os.path.dirname(os.path.abspath(__file__))


def runclean():
    subprocess.run(['bash', os.path.join(BASEDIR, 'clean.sh')], check=False)


def print_result(ok, label, output=''):
    status = 'PASS' if ok else 'FAIL'
    print(f'[{status}] {label}')

    if not ok and output:
        cleaned = output.strip()
        if cleaned:
            print(cleaned)

    return ok


def packet_loss_ok(output):
    return re.search(r',\s*0% packet loss', output) is not None


def extract_ipv4(output):
    match = re.search(r'\binet\s+(\d+\.\d+\.\d+\.\d+)/(\d+)', output)
    if not match:
        return None, None

    return match.group(1), int(match.group(2))


def run_hq_tests(net):
    passed = 0
    total = 0

    def test(ok, label, output=''):
        nonlocal passed, total
        total += 1
        if print_result(ok, label, output):
            passed += 1

    hit = net.get('hit')
    hdtest = net.get('hdtest')
    dhcphq = net.get('dhcphq')

    print('\n=== HQ autotest ===')

    dhcp_output = hdtest.cmd(
        'killall dhclient 2>/dev/null || true; '
        'timeout 25 dhclient -v hdtest-eth0 2>&1'
    )
    test('DHCPACK' in dhcp_output and 'bound to' in dhcp_output,
         'hdtest recibe IP por DHCP',
         dhcp_output)

    ip_output = hdtest.cmd('ip -4 -o addr show dev hdtest-eth0')
    assigned_ip, prefix_len = extract_ipv4(ip_output)
    test(assigned_ip is not None and prefix_len == 27 and assigned_ip.startswith('10.1.0.'),
         f'hdtest tiene IP valida de VLAN 10 ({assigned_ip or "sin IP"})',
         ip_output)

    route_output = hdtest.cmd('ip route')
    test('default via 10.1.0.1' in route_output,
         'hdtest recibe gateway 10.1.0.1 por DHCP',
         route_output)

    lease_output = dhcphq.cmd('cat tmp/dhcp_hq.leases 2>/dev/null')
    test(bool(assigned_ip) and assigned_ip in lease_output,
         f'lease DHCP registrada para {assigned_ip or "hdtest"}',
         lease_output)

    gateway_ping = hdtest.cmd('ping -c 3 -W 1 10.1.0.1')
    test(packet_loss_ok(gateway_ping),
         'hdtest hace ping a su gateway 10.1.0.1',
         gateway_ping)

    dns_ping = hdtest.cmd('ping -c 3 -W 1 10.1.0.10')
    test(packet_loss_ok(dns_ping),
         'hdtest hace ping al DNS 10.1.0.10',
         dns_ping)

    if assigned_ip:
        reverse_ping = hit.cmd(f'ping -c 3 -W 1 {assigned_ip}')
        test(packet_loss_ok(reverse_ping),
             f'hit hace ping a la IP asignada por DHCP ({assigned_ip})',
             reverse_ping)
    else:
        test(False, 'hit hace ping a la IP asignada por DHCP', ip_output)

    explicit_dns = hdtest.cmd('nslookup web.hq.local 10.1.0.10')
    test('Address: 10.1.0.11' in explicit_dns,
         'hdtest resuelve web.hq.local usando DNS 10.1.0.10',
         explicit_dns)

    default_dns = hdtest.cmd('nslookup web.hq.local')
    test('Address: 10.1.0.11' in default_dns,
         'hdtest resuelve web.hq.local usando su resolv.conf',
         default_dns)

    http_output = hdtest.cmd('curl --max-time 5 -s http://web.hq.local')
    test('MiniHub HQ Web Server' in http_output,
         'hdtest abre HTTP por dominio web.hq.local',
         http_output)

    print(f'\nResultado HQ autotest: {passed}/{total} pruebas pasaron')
    return passed == total


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

    ok = False

    try:
        hq = HQSite()
        hq.build(net)

        net.start()
        hq.configure()

        ok = run_hq_tests(net)
    finally:
        net.stop()
        runclean()

    return 0 if ok else 1


if __name__ == '__main__':
    setLogLevel('info')
    sys.exit(main())
