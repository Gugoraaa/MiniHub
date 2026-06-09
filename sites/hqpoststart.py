from router import Router
from switchL3 import SwitchL3


class HQPostStart:
    VLANS = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120]
    WANVLAN = 999

    SVIGATEWAYS = {
        10: '10.1.0.1/27',
        20: '10.1.0.33/27',
        30: '10.1.0.65/27',
        40: '10.1.0.97/27',
        50: '10.1.0.129/27',
        60: '10.1.0.161/27',
        70: '10.1.0.193/27',
        80: '10.1.1.1/27',
        90: '10.1.1.33/27',
        100: '10.1.1.65/27',
        110: '10.1.1.97/27',
        120: '10.1.1.129/27',
    }

    HOSTS = [
        ('hit', '10.1.0.2/27', '10.1.0.1', 1),
        ('hsales', '10.1.0.34/27', '10.1.0.33', 1),
        ('hsec', '10.1.0.66/27', '10.1.0.65', 1),
        ('hmgmt', '10.1.0.98/27', '10.1.0.97', 2),
        ('hhr', '10.1.0.130/27', '10.1.0.129', 2),
        ('hfin', '10.1.0.162/27', '10.1.0.161', 2),
        ('hinv', '10.1.0.194/27', '10.1.0.193', 3),
        ('hcust', '10.1.1.2/27', '10.1.1.1', 3),
        ('hpurch', '10.1.1.34/27', '10.1.1.33', 3),
        ('hcam', '10.1.1.66/27', '10.1.1.65', 4),
        ('hprint', '10.1.1.98/27', '10.1.1.97', 4),
        ('hphone', '10.1.1.130/27', '10.1.1.129', 4),
    ]

    def __init__(self):
        self.gateway = None
        self.mls = None
        self.hosts = {}
        self.switches = {}

    def build(self, net):
        self.gateway = net.addHost('hqr', cls=Router, ip=None)

        self.switches['dist'] = net.addSwitch('s0', failMode='standalone')
        self.switches['f1'] = net.addSwitch('s1', failMode='standalone')
        self.switches['f2'] = net.addSwitch('s2', failMode='standalone')
        self.switches['f3'] = net.addSwitch('s3', failMode='standalone')
        self.switches['f4'] = net.addSwitch('s4', failMode='standalone')
        self.mls = net.addSwitch('s5', cls=SwitchL3, failMode='standalone')

        for name, _, _, _ in self.HOSTS:
            self.hosts[name] = net.addHost(name, ip=None)

        return self

    def addlinks(self, net):
        hf1 = self.switches['f1']
        hf2 = self.switches['f2']
        hf3 = self.switches['f3']
        hf4 = self.switches['f4']
        hdist = self.switches['dist']

        net.addLink(self.hosts['hit'], hf1, port2=1)
        net.addLink(self.hosts['hsales'], hf1, port2=2)
        net.addLink(self.hosts['hsec'], hf1, port2=3)

        net.addLink(self.hosts['hmgmt'], hf2, port2=1)
        net.addLink(self.hosts['hhr'], hf2, port2=2)
        net.addLink(self.hosts['hfin'], hf2, port2=3)

        net.addLink(self.hosts['hinv'], hf3, port2=1)
        net.addLink(self.hosts['hcust'], hf3, port2=2)
        net.addLink(self.hosts['hpurch'], hf3, port2=3)

        net.addLink(self.hosts['hcam'], hf4, port2=1)
        net.addLink(self.hosts['hprint'], hf4, port2=2)
        net.addLink(self.hosts['hphone'], hf4, port2=3)

        net.addLink(hf1, hdist, port1=10, port2=1, bw=1000)
        net.addLink(hf2, hdist, port1=10, port2=2, bw=1000)
        net.addLink(hf3, hdist, port1=10, port2=3, bw=1000)
        net.addLink(hf4, hdist, port1=10, port2=4, bw=1000)

        net.addLink(hdist, self.mls, port1=24, port2=1, bw=1000)
        net.addLink(self.mls, self.gateway, port1=2, intfName2='hqr-eth0', bw=1000)

        return self

    def configurehosts(self):
        for name, cidr, gateway, _ in self.HOSTS:
            host = self.hosts[name]
            host.setIP(cidr)
            host.setDefaultRoute(f'via {gateway}')

        self.gateway.setIP('10.1.2.2/30', intf='hqr-eth0')
        self.gateway.cmd('ip link set hqr-eth0 up')

    def createsvi(self, vlanid, gatewaycidr, intfname=None):
        intfname = intfname or f'hqvlan{vlanid}'

        self.mls.cmd(
            f'ovs-vsctl --may-exist add-port {self.mls.name} {intfname} '
            f'tag={vlanid} -- set interface {intfname} type=internal'
        )

        self.mls.cmd(f'ip addr flush dev {intfname}')
        self.mls.cmd(f'ip addr add {gatewaycidr} dev {intfname}')
        self.mls.cmd(f'ip link set {intfname} up')

    def configure(self):
        self.configurehosts()

        allowedvlans = ','.join(str(vlan) for vlan in self.VLANS)
        hf1 = self.switches['f1']
        hf2 = self.switches['f2']
        hf3 = self.switches['f3']
        hf4 = self.switches['f4']
        hdist = self.switches['dist']

        hf1.cmd('ovs-vsctl set port s1-eth1 tag=10')
        hf1.cmd('ovs-vsctl set port s1-eth2 tag=20')
        hf1.cmd('ovs-vsctl set port s1-eth3 tag=30')
        hf1.cmd(f'ovs-vsctl set port s1-eth10 vlan_mode=trunk trunks={allowedvlans}')

        hf2.cmd('ovs-vsctl set port s2-eth1 tag=40')
        hf2.cmd('ovs-vsctl set port s2-eth2 tag=50')
        hf2.cmd('ovs-vsctl set port s2-eth3 tag=60')
        hf2.cmd(f'ovs-vsctl set port s2-eth10 vlan_mode=trunk trunks={allowedvlans}')

        hf3.cmd('ovs-vsctl set port s3-eth1 tag=70')
        hf3.cmd('ovs-vsctl set port s3-eth2 tag=80')
        hf3.cmd('ovs-vsctl set port s3-eth3 tag=90')
        hf3.cmd(f'ovs-vsctl set port s3-eth10 vlan_mode=trunk trunks={allowedvlans}')

        hf4.cmd('ovs-vsctl set port s4-eth1 tag=100')
        hf4.cmd('ovs-vsctl set port s4-eth2 tag=110')
        hf4.cmd('ovs-vsctl set port s4-eth3 tag=120')
        hf4.cmd(f'ovs-vsctl set port s4-eth10 vlan_mode=trunk trunks={allowedvlans}')

        hdist.cmd(f'ovs-vsctl set port s0-eth1 vlan_mode=trunk trunks={allowedvlans}')
        hdist.cmd(f'ovs-vsctl set port s0-eth2 vlan_mode=trunk trunks={allowedvlans}')
        hdist.cmd(f'ovs-vsctl set port s0-eth3 vlan_mode=trunk trunks={allowedvlans}')
        hdist.cmd(f'ovs-vsctl set port s0-eth4 vlan_mode=trunk trunks={allowedvlans}')
        hdist.cmd(f'ovs-vsctl set port s0-eth24 vlan_mode=trunk trunks={allowedvlans}')

        self.mls.cmd(f'ovs-vsctl set port s5-eth1 vlan_mode=trunk trunks={allowedvlans}')

        for vlanid, gatewaycidr in self.SVIGATEWAYS.items():
            self.createsvi(vlanid, gatewaycidr)

        self.mls.cmd(f'ovs-vsctl set port s5-eth2 tag={self.WANVLAN}')
        self.createsvi(self.WANVLAN, '10.1.2.1/30', intfname='hqwan')

        self.mls.cmd('ip route replace default via 10.1.2.2')
        self.gateway.cmd('ip route replace 10.1.0.0/23 via 10.1.2.1')

        return self
