from router import Router
from switchL3 import SwitchL3


class HQFix:
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

    def __init__(self):
        self.gateway = None
        self.mls = None

    def build(self, net):
        self.gateway = net.addHost('hqr', cls=Router, ip='10.1.2.2/30')

        hdist = net.addSwitch('s0', failMode='standalone')
        hf1 = net.addSwitch('s1', failMode='standalone')
        hf2 = net.addSwitch('s2', failMode='standalone')
        hf3 = net.addSwitch('s3', failMode='standalone')
        hf4 = net.addSwitch('s4', failMode='standalone')
        self.mls = net.addSwitch('s5', cls=SwitchL3, failMode='standalone')

        hit = net.addHost('hit', ip='10.1.0.2/27', defaultRoute='via 10.1.0.1')
        hsales = net.addHost('hsales', ip='10.1.0.34/27', defaultRoute='via 10.1.0.33')
        hsec = net.addHost('hsec', ip='10.1.0.66/27', defaultRoute='via 10.1.0.65')

        hmgmt = net.addHost('hmgmt', ip='10.1.0.98/27', defaultRoute='via 10.1.0.97')
        hhr = net.addHost('hhr', ip='10.1.0.130/27', defaultRoute='via 10.1.0.129')
        hfin = net.addHost('hfin', ip='10.1.0.162/27', defaultRoute='via 10.1.0.161')

        hinv = net.addHost('hinv', ip='10.1.0.194/27', defaultRoute='via 10.1.0.193')
        hcust = net.addHost('hcust', ip='10.1.1.2/27', defaultRoute='via 10.1.1.1')
        hpurch = net.addHost('hpurch', ip='10.1.1.34/27', defaultRoute='via 10.1.1.33')

        hcam = net.addHost('hcam', ip='10.1.1.66/27', defaultRoute='via 10.1.1.65')
        hprint = net.addHost('hprint', ip='10.1.1.98/27', defaultRoute='via 10.1.1.97')
        hphone = net.addHost('hphone', ip='10.1.1.130/27', defaultRoute='via 10.1.1.129')

        net.addLink(hit, hf1, port2=1)
        net.addLink(hsales, hf1, port2=2)
        net.addLink(hsec, hf1, port2=3)

        net.addLink(hmgmt, hf2, port2=1)
        net.addLink(hhr, hf2, port2=2)
        net.addLink(hfin, hf2, port2=3)

        net.addLink(hinv, hf3, port2=1)
        net.addLink(hcust, hf3, port2=2)
        net.addLink(hpurch, hf3, port2=3)

        net.addLink(hcam, hf4, port2=1)
        net.addLink(hprint, hf4, port2=2)
        net.addLink(hphone, hf4, port2=3)

        net.addLink(hf1, hdist, port1=10, port2=1, bw=1000)
        net.addLink(hf2, hdist, port1=10, port2=2, bw=1000)
        net.addLink(hf3, hdist, port1=10, port2=3, bw=1000)
        net.addLink(hf4, hdist, port1=10, port2=4, bw=1000)

        net.addLink(hdist, self.mls, port1=24, port2=1, bw=1000)
        net.addLink(self.mls, self.gateway, port1=2, intfName2='hqr-eth0', bw=1000)

        self.hdist = hdist
        self.hf1 = hf1
        self.hf2 = hf2
        self.hf3 = hf3
        self.hf4 = hf4

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
        allowedvlans = ','.join(str(vlan) for vlan in self.VLANS)

        self.hf1.cmd('ovs-vsctl set port s1-eth1 tag=10')
        self.hf1.cmd('ovs-vsctl set port s1-eth2 tag=20')
        self.hf1.cmd('ovs-vsctl set port s1-eth3 tag=30')
        self.hf1.cmd(f'ovs-vsctl set port s1-eth10 vlan_mode=trunk trunks={allowedvlans}')

        self.hf2.cmd('ovs-vsctl set port s2-eth1 tag=40')
        self.hf2.cmd('ovs-vsctl set port s2-eth2 tag=50')
        self.hf2.cmd('ovs-vsctl set port s2-eth3 tag=60')
        self.hf2.cmd(f'ovs-vsctl set port s2-eth10 vlan_mode=trunk trunks={allowedvlans}')

        self.hf3.cmd('ovs-vsctl set port s3-eth1 tag=70')
        self.hf3.cmd('ovs-vsctl set port s3-eth2 tag=80')
        self.hf3.cmd('ovs-vsctl set port s3-eth3 tag=90')
        self.hf3.cmd(f'ovs-vsctl set port s3-eth10 vlan_mode=trunk trunks={allowedvlans}')

        self.hf4.cmd('ovs-vsctl set port s4-eth1 tag=100')
        self.hf4.cmd('ovs-vsctl set port s4-eth2 tag=110')
        self.hf4.cmd('ovs-vsctl set port s4-eth3 tag=120')
        self.hf4.cmd(f'ovs-vsctl set port s4-eth10 vlan_mode=trunk trunks={allowedvlans}')

        self.hdist.cmd(f'ovs-vsctl set port s0-eth1 vlan_mode=trunk trunks={allowedvlans}')
        self.hdist.cmd(f'ovs-vsctl set port s0-eth2 vlan_mode=trunk trunks={allowedvlans}')
        self.hdist.cmd(f'ovs-vsctl set port s0-eth3 vlan_mode=trunk trunks={allowedvlans}')
        self.hdist.cmd(f'ovs-vsctl set port s0-eth4 vlan_mode=trunk trunks={allowedvlans}')
        self.hdist.cmd(f'ovs-vsctl set port s0-eth24 vlan_mode=trunk trunks={allowedvlans}')

        self.mls.cmd(f'ovs-vsctl set port s5-eth1 vlan_mode=trunk trunks={allowedvlans}')

        for vlanid, gatewaycidr in self.SVIGATEWAYS.items():
            self.createsvi(vlanid, gatewaycidr)

        # Transit VLAN toward the WAN router. The IP lives on an OVS internal
        # interface, not directly on the physical OVS port.
        self.mls.cmd(f'ovs-vsctl set port s5-eth2 tag={self.WANVLAN}')
        self.createsvi(self.WANVLAN, '10.1.2.1/30', intfname='hqwan')

        self.gateway.setIP('10.1.2.2/30', intf='hqr-eth0')
        self.gateway.cmd('ip link set hqr-eth0 up')

        self.mls.cmd('ip route replace default via 10.1.2.2')
        self.gateway.cmd('ip route replace 10.1.0.0/23 via 10.1.2.1')

        return self
