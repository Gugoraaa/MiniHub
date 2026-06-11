import re

from mininet.net import Mininet
from mininet.node import OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel

from sites.tiendaSanPedro import TiendaSanPedro
from validate_network import dhcp_renew, ping_test, process_running

# host, vlan, gateway, label, prefijo_ip_dhcp, mascara_cidr
SP_VLAN_HOSTS = [
    ('sp_hwifi',  130, '10.3.0.1',   'WiFi',       '10.3.0.',  24),
    ('sp_hchk',   140, '10.3.1.1',   'Checkout',   '10.3.1.',  27),
    ('sp_hadmin', 40,  '10.3.1.33',  'Admin',      '10.3.1.',  29),
    ('sp_hsec',   30,  '10.3.1.41',  'Security',   '10.3.1.',  29),
    ('sp_hcam',   100, '10.3.1.49',  'Cámaras',    '10.3.1.',  25),
    ('sp_hprint', 110, '10.3.1.113', 'Impresoras', '10.3.1.',  28),
    ('sp_hphone', 120, '10.3.1.129', 'Teléfonos',  '10.3.1.',  29),
]


class SanPedroTestSuite:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

    def __init__(self):
        self._results = []

    def _record(self, ok):
        self._results.append(ok)

    def _header(self, title):
        sep = '=' * 64
        print('\n' + self.BOLD + sep + self.RESET)
        print(self.BOLD + f'  {title}' + self.RESET)
        print(sep)

    def _status_line(self, ok, label, detail=''):
        self._record(ok)
        status = self.GREEN + 'PASS' + self.RESET if ok else self.RED + 'FAIL' + self.RESET
        line = f'  [{status}] {label}'
        if detail:
            line += f'  ({detail})'
        print(line)

    def _ping_loss(self, net, src_name, dst, label):
        src = net.get(src_name)
        out = src.cmd(f'ping -c 3 -W 2 {dst}')
        match = re.search(r'(\d+)% packet loss', out)
        loss = int(match.group(1)) if match else 100
        ok = loss == 0
        self._status_line(ok, label, f'{loss}% loss')
        return ok

    def run(self, net):
        self._results = []

        self._header('A. SERVICIOS DHCP')
        self._record(process_running(
            net, 'dhcp_sp', 'dnsmasq', 'dnsmasq activo en dhcp_sp'
        ))
        self._record(process_running(
            net, 's16', 'dhcrelay', 'dhcrelay activo en s16'
        ))
        self._record(ping_test(
            net, 'dhcp_sp', '192.168.105.254',
            label='dhcp_sp -> gateway VLAN 998 (s16)'
        ))

        self._header('B. LEASE DHCP POR VLAN')
        for host, _, gateway, _, prefix, cidr in SP_VLAN_HOSTS:
            self._record(dhcp_renew(
                net,
                host,
                f'{host}-eth0',
                prefix,
                cidr,
                gateway,
            ))

        self._header('C. HOST -> GATEWAY (SVI en s16)')
        for host, vlan, gateway, label, _, _ in SP_VLAN_HOSTS:
            self._ping_loss(
                net, host, gateway,
                f'{host} -> {gateway}  [VLAN {vlan} {label}]'
            )

        self._header('D. MATRIZ INTER-VLAN')
        for src_host, src_vlan, _, src_label, _, _ in SP_VLAN_HOSTS:
            for dst_host, dst_vlan, _, dst_label, _, _ in SP_VLAN_HOSTS:
                if src_host == dst_host:
                    continue
                self._ping_loss(
                    net, src_host, dst_host,
                    f'{src_host} (VLAN {src_vlan} {src_label}) -> '
                    f'{dst_host} (VLAN {dst_vlan} {dst_label})'
                )

        passed = sum(self._results)
        total = len(self._results)
        color = (
            self.GREEN if passed == total
            else self.YELLOW if passed >= total * 0.7
            else self.RED
        )
        sep = '=' * 64
        print('\n' + sep)
        print(f'  RESULTADO: {self.BOLD}{color}{passed} / {total} tests pasaron{self.RESET}')
        print(sep + '\n')

        return passed == total


def print_suggested_ping_commands():
    print('\n=== Tienda San Pedro — comandos manuales en Mininet CLI ===')
    print('\n--- DHCP ---')
    for host, _, _, label, _, _ in SP_VLAN_HOSTS:
        print(f'  {host} dhclient -v {host}-eth0   # VLAN ({label})')

    print('\n--- Gateway ---')
    for host, vlan, gateway, label, _, _ in SP_VLAN_HOSTS:
        print(f'  {host:<12} ping -c 3 {gateway:<14} # VLAN {vlan} ({label})')

    print('\n--- Inter-VLAN ---')
    for src_host, src_vlan, _, src_label, _, _ in SP_VLAN_HOSTS:
        for dst_host, dst_vlan, _, dst_label, _, _ in SP_VLAN_HOSTS:
            if src_host == dst_host:
                continue
            print(
                f'  {src_host:<12} ping -c 3 {dst_host:<12} '
                f'# VLAN {src_vlan} ({src_label}) -> VLAN {dst_vlan} ({dst_label})'
            )
    print('============================================================\n')


def run():
    net = Mininet(
        controller=None,
        switch=OVSSwitch,
        autoSetMacs=True,
        autoStaticArp=False
    )

    site = TiendaSanPedro()
    site.build(net)

    net.start()

    site.configure()

    SanPedroTestSuite().run(net)
    print_suggested_ping_commands()

    CLI(net)

    site.stop_services()
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    run()
