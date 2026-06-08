import re
import time


class TestSuite:
    GREEN  = '\033[92m'
    RED    = '\033[91m'
    YELLOW = '\033[93m'
    BOLD   = '\033[1m'
    RESET  = '\033[0m'

    def __init__(self):
        self._results = []

    def _ping(self, net, src_name, dst_name, expect_ok):
        src = net.get(src_name)
        dst = net.get(dst_name)
        out = src.cmd('ping -c 3 -W 2 %s' % dst.IP())
        m = re.search(r'(\d+)% packet loss', out)
        loss = int(m.group(1)) if m else 100
        ok = (loss == 0) if expect_ok else (loss == 100)  # 100% loss = completamente bloqueado
        self._results.append(ok)
        tag    = 'FUNCIONA' if expect_ok else 'BLOQUEADO'
        status = self.GREEN + 'PASS' + self.RESET if ok else self.RED + 'FAIL' + self.RESET
        print('  [%s] %-48s  %d%% loss' % (
            status, '%s -> %s  [%s]' % (src_name, dst_name, tag), loss))

    def _iperf(self, net, label, server_name, client_name, server_ip, limit_mbps):
        sv = net.get(server_name)
        cl = net.get(client_name)
        sv.cmd('pkill -f "iperf -s" 2>/dev/null; iperf -s &')
        time.sleep(1)
        out = cl.cmd('iperf -c %s -t 5' % server_ip)
        sv.cmd('pkill -f "iperf -s" 2>/dev/null')
        m = re.search(r'([\d.]+)\s+Mbits/sec', out)
        mbps = float(m.group(1)) if m else 0.0
        ok = 0 < mbps <= limit_mbps * 1.2  # 20% de tolerancia sobre el limite configurado
        self._results.append(ok)
        status = self.GREEN + 'PASS' + self.RESET if ok else self.RED + 'FAIL' + self.RESET
        print('  [%s] %-48s  %.1f Mbps  (limite %d Mbps)' % (status, label, mbps, limit_mbps))

    def run(self, net):
        self._results = []
        sep = '=' * 64

        print('\n' + self.BOLD + sep + self.RESET)
        print(self.BOLD + '  A. CONNECTIVITY TESTS  (deben FUNCIONAR)' + self.RESET)
        print(sep)
        self._ping(net, 'h_t1_checkout',         'h_hq_sales',     True)
        self._ping(net, 'h_t2_checkout',         'h_hq_sales',     True)
        self._ping(net, 'wh_inventory_control_01', 'h_hq_inventory', True)
        self._ping(net, 'h_hq_it',               'wh_warehouse_office_01', True)
        self._ping(net, 'h_t1_checkout',         'wh_inventory_control_01', True)

        print('\n' + self.BOLD + sep + self.RESET)
        print(self.BOLD + '  B. SECURITY TESTS  (firewall iptables)' + self.RESET)
        print(sep)
        self._ping(net, 'h_t1_wifi_guest',       'h_hq_sales',     False)
        self._ping(net, 'h_hq_sales',            'h_hq_printer',   False)
        self._ping(net, 'h_hq_customer_service', 'h_hq_finance',   False)
        self._ping(net, 'h_hq_security_ops',     'h_hq_camera',    True)
        self._ping(net, 'h_hq_sales',            'h_hq_camera',    False)

        print('\n' + self.BOLD + sep + self.RESET)
        print(self.BOLD + '  C. BANDWIDTH TESTS  (iperf / TCLink)' + self.RESET)
        print(sep)
        self._iperf(net, 'HQ sales  <- T1 checkout    (WAN 20 Mbps)',
                    'h_hq_sales',     'h_t1_checkout',  '10.1.0.40',  20)
        self._iperf(net, 'HQ inventory <- WH inventory (WAN 50 Mbps)',
                    'h_hq_inventory', 'h_wh_inventory', '10.1.0.200', 50)
        self._iperf(net, 'WH inventory <- T1 checkout  (directo 15 Mbps)',
                    'wh_inventory_control_01', 'h_t1_checkout', '10.4.0.2', 15)

        passed = sum(self._results)
        total  = len(self._results)
        color  = self.GREEN if passed == total else (self.YELLOW if passed >= total * 0.7 else self.RED)
        print('\n' + sep)
        print('  RESULTADO: %s%s%d / %d tests pasaron%s' % (self.BOLD, color, passed, total, self.RESET))
        print(sep + '\n')

    def dump_diagnostics(self, routers):
        sep = '-' * 64
        for name in ['r_hq', 'r_t1', 'r_t2', 'wh_r']:
            r = routers[name]
            print('\n%s\n  DIAG %s\n%s' % (sep, name, sep))
            print('[ip -br -4 addr]')
            print(r.cmd('ip -br -4 addr').rstrip())
            print('[ip route]')
            print(r.cmd('ip route').rstrip())
        print('\n%s\n  DIAG r_hq iptables FORWARD\n%s' % (sep, sep))
        print(routers['r_hq'].cmd('iptables -S FORWARD').rstrip())
        print(sep + '\n')

    def print_suggested_commands(self):
        print('\n' + '=' * 60)
        print('MiniHUB listo. Comandos sugeridos dentro de la CLI de Mininet:')
        print('=' * 60)
        print('=== Connectivity Tests (deben FUNCIONAR) ===')
        print('h_t1_checkout ping -c 3 h_hq_sales')
        print('h_t2_checkout ping -c 3 h_hq_sales')
        print('h_wh_inventory ping -c 3 h_hq_inventory')
        print('h_hq_it ping -c 3 h_wh_admin')
        print('h_t1_checkout ping -c 3 h_wh_inventory')
        print('\n=== Security Tests (firewall) ===')
        print('h_t1_wifi_guest ping -c 3 h_hq_sales         # debe FALLAR')
        print('h_hq_sales ping -c 3 h_hq_printer            # debe FALLAR')
        print('h_hq_customer_service ping -c 3 h_hq_finance # debe FALLAR')
        print('h_hq_security_ops ping -c 3 h_hq_camera      # debe FUNCIONAR')
        print('h_hq_sales ping -c 3 h_hq_camera             # debe FALLAR')
        print('\n=== Bandwidth Tests (iperf) ===')
        print('h_hq_sales iperf -s &')
        print('h_t1_checkout iperf -c 10.1.0.40 -t 10       # ~20 Mbps')
        print('h_hq_inventory iperf -s &')
        print('h_wh_inventory iperf -c 10.1.0.200 -t 10     # ~50 Mbps')
        print('h_wh_inventory iperf -s &')
        print('h_t1_checkout iperf -c 10.4.0.10 -t 10       # ~15 Mbps (enlace directo)')
        print('\n=== DHCP Demo ===')
        print('h_hq_sales ip addr flush dev h_hq_sales-eth0')
        print('h_hq_sales dhclient -v h_hq_sales-eth0')
        print('h_hq_sales ip addr')
        print('=' * 60 + '\n')
