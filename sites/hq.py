from router import Router
from switchL3 import SwitchL3


class HQSite:
    VLANS = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120]

    SVI_GATEWAYS = {
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
        # HQ router WAN
        self.gateway = net.addHost('hqr', cls=Router, ip=None)

        # Distribution switch
        hq_dist = net.addSwitch('s0', failMode='standalone')

        # Access switches - one per floor
        hq_f1 = net.addSwitch('s1', failMode='standalone')
        hq_f2 = net.addSwitch('s2', failMode='standalone')
        hq_f3 = net.addSwitch('s3', failMode='standalone')
        hq_f4 = net.addSwitch('s4', failMode='standalone')

        # Switch capa 3 / multilayer
        self.mls = net.addSwitch('s5', cls=SwitchL3, failMode='standalone')

        # Floor 1 representative hosts
        hit = net.addHost('hit', ip='10.1.0.2/27', defaultRoute='via 10.1.0.1')
        hsales = net.addHost('hsales', ip='10.1.0.34/27', defaultRoute='via 10.1.0.33')
        hsec = net.addHost('hsec', ip='10.1.0.66/27', defaultRoute='via 10.1.0.65')

        # Floor 2 representative hosts
        hmgmt = net.addHost('hmgmt', ip='10.1.0.98/27', defaultRoute='via 10.1.0.97')
        hhr = net.addHost('hhr', ip='10.1.0.130/27', defaultRoute='via 10.1.0.129')
        hfin = net.addHost('hfin', ip='10.1.0.162/27', defaultRoute='via 10.1.0.161')

        # Floor 3 representative hosts
        hinv = net.addHost('hinv', ip='10.1.0.194/27', defaultRoute='via 10.1.0.193')
        hcust = net.addHost('hcust', ip='10.1.1.2/27', defaultRoute='via 10.1.1.1')
        hpurch = net.addHost('hpurch', ip='10.1.1.34/27', defaultRoute='via 10.1.1.33')

        # Floor 4 representative hosts
        hcam = net.addHost('hcam', ip='10.1.1.66/27', defaultRoute='via 10.1.1.65')
        hprint = net.addHost('hprint', ip='10.1.1.98/27', defaultRoute='via 10.1.1.97')
        hphone = net.addHost('hphone', ip='10.1.1.130/27', defaultRoute='via 10.1.1.129')

        # Host-to-access-switch links
        net.addLink(hit, hq_f1, port2=1)
        net.addLink(hsales, hq_f1, port2=2)
        net.addLink(hsec, hq_f1, port2=3)

        net.addLink(hmgmt, hq_f2, port2=1)
        net.addLink(hhr, hq_f2, port2=2)
        net.addLink(hfin, hq_f2, port2=3)

        net.addLink(hinv, hq_f3, port2=1)
        net.addLink(hcust, hq_f3, port2=2)
        net.addLink(hpurch, hq_f3, port2=3)

        net.addLink(hcam, hq_f4, port2=1)
        net.addLink(hprint, hq_f4, port2=2)
        net.addLink(hphone, hq_f4, port2=3)

        # Access switches to distribution
        net.addLink(hq_f1, hq_dist, port1=10, port2=1, bw=1000)
        net.addLink(hq_f2, hq_dist, port1=10, port2=2, bw=1000)
        net.addLink(hq_f3, hq_dist, port1=10, port2=3, bw=1000)
        net.addLink(hq_f4, hq_dist, port1=10, port2=4, bw=1000)

        # Distribution to L3 switch, then L3 switch to WAN router
        net.addLink(hq_dist, self.mls, port1=24, port2=1, bw=1000)
        net.addLink(self.mls, self.gateway, port1=2, intfName2='hqr-eth0', bw=1000)

        # Save switches needed later for configure()
        self.hq_dist = hq_dist
        self.hq_f1 = hq_f1
        self.hq_f2 = hq_f2
        self.hq_f3 = hq_f3
        self.hq_f4 = hq_f4

    def create_svi(self, vlan_id, gateway_cidr):
        intf_name = f'hqvlan{vlan_id}'

        self.mls.cmd(
            f'ovs-vsctl --may-exist add-port {self.mls.name} {intf_name} '
            f'tag={vlan_id} -- set interface {intf_name} type=internal'
        )

        self.mls.cmd(f'ip addr flush dev {intf_name}')
        self.mls.cmd(f'ip addr add {gateway_cidr} dev {intf_name}')
        self.mls.cmd(f'ip link set {intf_name} up')

    def configure(self):
        allowed_vlans = ','.join(str(vlan) for vlan in self.VLANS)

        # Access ports - Floor 1
        self.hq_f1.cmd('ovs-vsctl set port s1-eth1 tag=10')
        self.hq_f1.cmd('ovs-vsctl set port s1-eth2 tag=20')
        self.hq_f1.cmd('ovs-vsctl set port s1-eth3 tag=30')
        self.hq_f1.cmd(f'ovs-vsctl set port s1-eth10 vlan_mode=trunk trunks={allowed_vlans}')

        # Access ports - Floor 2
        self.hq_f2.cmd('ovs-vsctl set port s2-eth1 tag=40')
        self.hq_f2.cmd('ovs-vsctl set port s2-eth2 tag=50')
        self.hq_f2.cmd('ovs-vsctl set port s2-eth3 tag=60')
        self.hq_f2.cmd(f'ovs-vsctl set port s2-eth10 vlan_mode=trunk trunks={allowed_vlans}')

        # Access ports - Floor 3
        self.hq_f3.cmd('ovs-vsctl set port s3-eth1 tag=70')
        self.hq_f3.cmd('ovs-vsctl set port s3-eth2 tag=80')
        self.hq_f3.cmd('ovs-vsctl set port s3-eth3 tag=90')
        self.hq_f3.cmd(f'ovs-vsctl set port s3-eth10 vlan_mode=trunk trunks={allowed_vlans}')

        # Access ports - Floor 4
        self.hq_f4.cmd('ovs-vsctl set port s4-eth1 tag=100')
        self.hq_f4.cmd('ovs-vsctl set port s4-eth2 tag=110')
        self.hq_f4.cmd('ovs-vsctl set port s4-eth3 tag=120')
        self.hq_f4.cmd(f'ovs-vsctl set port s4-eth10 vlan_mode=trunk trunks={allowed_vlans}')

        # Distribution trunks
        self.hq_dist.cmd(f'ovs-vsctl set port s0-eth1 vlan_mode=trunk trunks={allowed_vlans}')
        self.hq_dist.cmd(f'ovs-vsctl set port s0-eth2 vlan_mode=trunk trunks={allowed_vlans}')
        self.hq_dist.cmd(f'ovs-vsctl set port s0-eth3 vlan_mode=trunk trunks={allowed_vlans}')
        self.hq_dist.cmd(f'ovs-vsctl set port s0-eth4 vlan_mode=trunk trunks={allowed_vlans}')
        self.hq_dist.cmd(f'ovs-vsctl set port s0-eth24 vlan_mode=trunk trunks={allowed_vlans}')

        # L3 switch trunk toward distribution
        self.mls.cmd(f'ovs-vsctl set port s5-eth1 vlan_mode=trunk trunks={allowed_vlans}')

        # Gateways / SVIs on the L3 switch
        for vlan_id, gateway_cidr in self.SVI_GATEWAYS.items():
            self.create_svi(vlan_id, gateway_cidr)

        # Transit link L3 switch -> WAN router
        self.mls.cmd('ip addr flush dev s5-eth2')
        self.mls.cmd('ip addr add 10.1.2.1/30 dev s5-eth2')
        self.mls.cmd('ip link set s5-eth2 up')

        self.gateway.cmd('ip addr flush dev hqr-eth0')
        self.gateway.cmd('ip addr add 10.1.2.2/30 dev hqr-eth0')
        self.gateway.cmd('ip link set hqr-eth0 up')

        # Routes
        self.mls.cmd('ip route replace default via 10.1.2.2')
        self.gateway.cmd('ip route replace 10.1.0.0/23 via 10.1.2.1')

        return self
