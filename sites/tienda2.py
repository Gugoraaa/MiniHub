from mininet.net import Mininet
from mininet.node import OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel

from router import Router
from switchL3 import SwitchL3
from services.dhcp_server import DHCPServer


class Tienda2:
    VLANS = [130, 140, 40, 30, 100, 110, 120]
    DHCP_VLAN = 998

    def __init__(self, net):
        self.net = net


        self.sw_piso1 = net.addSwitch('s10', failMode='standalone')
        self.sw_piso2 = net.addSwitch('s11', failMode='standalone')
        self.mls = net.addSwitch('s12', cls=SwitchL3, failMode='standalone')
        self.r = net.addHost('r_t2', cls=Router, ip=None)


        self.dhcp = DHCPServer(
            net=net,
            name='dhcp_t2',
            ip_cidr='192.168.103.10/24',
            gateway='192.168.103.254',
            conf_path='tmp/dhcp_tienda2.conf',
            pid_path='tmp/dhcp_tienda2.pid',
            lease_path='tmp/dhcp_tienda2.leases',
            log_path='tmp/dhcp_tienda2.log'
        )


        self.checkout = net.addHost('checkout', ip=None)
        self.tprt = net.addHost('tprt', ip=None)
        self.cam_ck = net.addHost('cam_ck', ip=None)
        self.ap_sec = net.addHost('ap_sec', ip=None)
        self.alarm = net.addHost('alarm', ip=None)
        self.cam_se = net.addHost('cam_se', ip=None)
        self.ap_sh = net.addHost('ap_sh', ip=None)
        self.cam_sh = net.addHost('cam_sh', ip=None)

        net.addLink(self.checkout, self.sw_piso1)
        net.addLink(self.tprt, self.sw_piso1)
        net.addLink(self.cam_ck, self.sw_piso1)
        net.addLink(self.ap_sec, self.sw_piso1)
        net.addLink(self.alarm, self.sw_piso1)
        net.addLink(self.cam_se, self.sw_piso1)
        net.addLink(self.ap_sh, self.sw_piso1)
        net.addLink(self.cam_sh, self.sw_piso1)
        net.addLink(self.sw_piso1, self.mls)


        self.pc_admin = net.addHost('pc_admin', ip=None)
        self.phone = net.addHost('phone', ip=None)
        self.adprt = net.addHost('adprt', ip=None)
        self.cam_ad = net.addHost('cam_ad', ip=None)

        net.addLink(self.pc_admin, self.sw_piso2)
        net.addLink(self.phone, self.sw_piso2)
        net.addLink(self.adprt, self.sw_piso2)
        net.addLink(self.cam_ad, self.sw_piso2)
        net.addLink(self.sw_piso2, self.mls)


        net.addLink(self.dhcp.host, self.mls, intfName1='dhcp_t2-eth0')
        net.addLink(self.mls, self.r, intfName2='r_t2-wan')

    def client_hosts(self):
        return (
            self.checkout, self.tprt, self.cam_ck, self.ap_sec,
            self.alarm, self.cam_se, self.ap_sh, self.cam_sh,
            self.pc_admin, self.phone, self.adprt, self.cam_ad
        )

    def create_svi(self, vlan_id, gateway_cidr):
        intf = f't2_vlan{vlan_id}'

        self.mls.cmd(
            f'ovs-vsctl --may-exist add-port {self.mls.name} {intf} '
            f'tag={vlan_id} -- set interface {intf} type=internal'
        )

        self.mls.cmd(f'ip addr flush dev {intf}')
        self.mls.cmd(f'ip addr add {gateway_cidr} dev {intf}')
        self.mls.cmd(f'ip link set {intf} up')

    def configure(self):
        allowed = ','.join(str(vlan) for vlan in self.VLANS)

        self.mls.cmd('sysctl -w net.ipv4.ip_forward=1')
        self.mls.cmd('sysctl -w net.ipv4.conf.all.rp_filter=0')
        self.mls.cmd('sysctl -w net.ipv4.conf.default.rp_filter=0')
        self.mls.cmd('iptables -P FORWARD ACCEPT')
        self.mls.cmd('iptables -F FORWARD')


        self.sw_piso1.cmd('ovs-vsctl set port s10-eth1 tag=140')
        self.sw_piso1.cmd('ovs-vsctl set port s10-eth2 tag=110')
        self.sw_piso1.cmd('ovs-vsctl set port s10-eth3 tag=100')
        self.sw_piso1.cmd('ovs-vsctl set port s10-eth4 tag=130')
        self.sw_piso1.cmd('ovs-vsctl set port s10-eth5 tag=30')
        self.sw_piso1.cmd('ovs-vsctl set port s10-eth6 tag=100')
        self.sw_piso1.cmd('ovs-vsctl set port s10-eth7 tag=130')
        self.sw_piso1.cmd('ovs-vsctl set port s10-eth8 tag=100')
        self.sw_piso1.cmd(f'ovs-vsctl set port s10-eth9 vlan_mode=trunk trunks={allowed}')


        self.sw_piso2.cmd('ovs-vsctl set port s11-eth1 tag=40')
        self.sw_piso2.cmd('ovs-vsctl set port s11-eth2 tag=120')
        self.sw_piso2.cmd('ovs-vsctl set port s11-eth3 tag=110')
        self.sw_piso2.cmd('ovs-vsctl set port s11-eth4 tag=100')
        self.sw_piso2.cmd(f'ovs-vsctl set port s11-eth5 vlan_mode=trunk trunks={allowed}')


        self.mls.cmd(f'ovs-vsctl set port s12-eth1 vlan_mode=trunk trunks={allowed}')
        self.mls.cmd(f'ovs-vsctl set port s12-eth2 vlan_mode=trunk trunks={allowed}')
        self.mls.cmd(f'ovs-vsctl set port s12-eth3 tag={self.DHCP_VLAN}')


        self.create_svi(130, '10.3.0.1/24')
        self.create_svi(140, '10.3.1.1/27')
        self.create_svi(40, '10.3.1.33/28')
        self.create_svi(30, '10.3.1.49/28')
        self.create_svi(100, '10.3.1.65/28')
        self.create_svi(110, '10.3.1.81/29')
        self.create_svi(120, '10.3.1.89/30')


        self.create_svi(self.DHCP_VLAN, '192.168.103.254/24')

        self.dhcp.host.cmd('ip addr flush dev dhcp_t2-eth0')
        self.dhcp.host.setIP('192.168.103.10/24', intf='dhcp_t2-eth0')
        self.dhcp.host.cmd('ip link set dhcp_t2-eth0 up')
        self.dhcp.host.cmd('ip route replace default via 192.168.103.254')


        self.mls.cmd('ip addr flush dev s12-eth4')
        self.mls.cmd('ip addr add 10.3.1.249/30 dev s12-eth4')
        self.mls.cmd('ip link set s12-eth4 up')

        self.r.cmd('ip addr flush dev r_t2-wan')
        self.r.cmd('ip addr add 10.3.1.250/30 dev r_t2-wan')
        self.r.cmd('ip link set r_t2-wan up')

        self.mls.cmd('ip route replace default via 10.3.1.250')
        self.r.cmd('ip route replace 10.3.0.0/23 via 10.3.1.249')
        self.r.cmd('ip route replace 192.168.103.0/24 via 10.3.1.249')

        self.dhcp.start()


        self.mls.cmd(
            'dhcrelay -4 '
            '-i t2_vlan130 '
            '-i t2_vlan140 '
            '-i t2_vlan40 '
            '-i t2_vlan30 '
            '-i t2_vlan100 '
            '-i t2_vlan110 '
            '-i t2_vlan120 '
            '-i t2_vlan998 '
            '192.168.103.10'
        )
        self.mls.cmd('sleep 1')

        self.start_dhcp_clients()

        return self

    def start_dhcp_clients(self):
        for host in self.client_hosts():
            intf = host.defaultIntf().name
            pid_path = f'tmp/dhclient-{host.name}.pid'
            lease_path = f'tmp/dhclient-{host.name}.leases'
            log_path = f'tmp/dhclient-{host.name}.log'

            host.cmd(f'touch {lease_path} {log_path}')
            host.cmd(f'test ! -f {pid_path} || kill $(cat {pid_path}) 2>/dev/null || true')
            host.cmd(f'dhclient -4 -r -pf {pid_path} -lf {lease_path} {intf} >/dev/null 2>&1 || true')
            host.cmd(f'ip addr flush dev {intf}')
            host.cmd(f'ip link set {intf} up')
            host.cmd(
                f'timeout 20 dhclient -4 -1 -v '
                f'-pf {pid_path} '
                f'-lf {lease_path} '
                f'{intf} >{log_path} 2>&1'
            )

    def stop_services(self):
        self.mls.cmd('killall dhcrelay 2>/dev/null || true')
        self.dhcp.stop()

        for host in self.client_hosts():
            host.cmd(f'test ! -f tmp/dhclient-{host.name}.pid || kill $(cat tmp/dhclient-{host.name}.pid) 2>/dev/null || true')


def run():
    net = Mininet(
        controller=None,
        switch=OVSSwitch,
        autoSetMacs=True,
        autoStaticArp=False,
    )

    t2 = Tienda2(net)
    net.start()
    t2.configure()

    print('\n=== Tienda 2 topology loaded ===')
    print('Clientes DHCP iniciados automaticamente en todos los hosts de Tienda 2.')
    print('Pruebas sugeridas dentro de Mininet:')
    print('  checkout ping -c 3 10.3.1.1')
    print('  checkout ping -c 3 pc_admin')
    print('  dhcp_t2 ping -c 3 192.168.103.254')
    print('================================\n')

    CLI(net)
    t2.stop_services()
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    run()
