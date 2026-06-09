from mininet.node import Node


class Router(Node):

    def config(self, **params):
        super(Router, self).config(**params)
        self.cmd('sysctl -w net.ipv4.ip_forward=1')
        self.cmd('modprobe 8021q')

    def terminate(self):
        self.cmd('sysctl -w net.ipv4.ip_forward=0')
        super(Router, self).terminate()


class HQSite:

    def __init__(self):
        self.gateway = None

    def build(self, net):
        # HQ router
        self.gateway = net.addHost('hq_r', cls=Router)

        # HQ core / Distribution switch
        hq_core = net.addSwitch('s0', failMode='standalone')

        # HQ access switches - one per floor
        hq_f1 = net.addSwitch('s1', failMode='standalone')
        hq_f2 = net.addSwitch('s2', failMode='standalone')
        hq_f3 = net.addSwitch('s3', failMode='standalone')
        hq_f4 = net.addSwitch('s4', failMode='standalone')

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

        # Access switches to HQ core
        net.addLink(hq_f1, hq_core, port1=10, port2=1, bw=1000)
        net.addLink(hq_f2, hq_core, port1=10, port2=2, bw=1000)
        net.addLink(hq_f3, hq_core, port1=10, port2=3, bw=1000)
        net.addLink(hq_f4, hq_core, port1=10, port2=4, bw=1000)

        # HQ core to HQ router trunk
        net.addLink(hq_core, self.gateway, port1=24, intfName2='hq_r-eth0', bw=1000)

        # Save switches needed later for configure()
        self.hq_core = hq_core
        self.hq_f1 = hq_f1
        self.hq_f2 = hq_f2
        self.hq_f3 = hq_f3
        self.hq_f4 = hq_f4

    def configure(self):
        vlans = '10,20,30,40,50,60,70,80,90,100,110,120'

        # Access ports - Floor 1
        self.hq_f1.cmd('ovs-vsctl set port s1-eth1 tag=10')
        self.hq_f1.cmd('ovs-vsctl set port s1-eth2 tag=20')
        self.hq_f1.cmd('ovs-vsctl set port s1-eth3 tag=30')
        self.hq_f1.cmd('ovs-vsctl set port s1-eth10 vlan_mode=trunk trunks=%s' % vlans)

        # Access ports - Floor 2
        self.hq_f2.cmd('ovs-vsctl set port s2-eth1 tag=40')
        self.hq_f2.cmd('ovs-vsctl set port s2-eth2 tag=50')
        self.hq_f2.cmd('ovs-vsctl set port s2-eth3 tag=60')
        self.hq_f2.cmd('ovs-vsctl set port s2-eth10 vlan_mode=trunk trunks=%s' % vlans)

        # Access ports - Floor 3
        self.hq_f3.cmd('ovs-vsctl set port s3-eth1 tag=70')
        self.hq_f3.cmd('ovs-vsctl set port s3-eth2 tag=80')
        self.hq_f3.cmd('ovs-vsctl set port s3-eth3 tag=90')
        self.hq_f3.cmd('ovs-vsctl set port s3-eth10 vlan_mode=trunk trunks=%s' % vlans)

        # Access ports - Floor 4
        self.hq_f4.cmd('ovs-vsctl set port s4-eth1 tag=100')
        self.hq_f4.cmd('ovs-vsctl set port s4-eth2 tag=110')
        self.hq_f4.cmd('ovs-vsctl set port s4-eth3 tag=120')
        self.hq_f4.cmd('ovs-vsctl set port s4-eth10 vlan_mode=trunk trunks=%s' % vlans)

        # Core switch trunks
        self.hq_core.cmd('ovs-vsctl set port s0-eth1 vlan_mode=trunk trunks=%s' % vlans)
        self.hq_core.cmd('ovs-vsctl set port s0-eth2 vlan_mode=trunk trunks=%s' % vlans)
        self.hq_core.cmd('ovs-vsctl set port s0-eth3 vlan_mode=trunk trunks=%s' % vlans)
        self.hq_core.cmd('ovs-vsctl set port s0-eth4 vlan_mode=trunk trunks=%s' % vlans)
        self.hq_core.cmd('ovs-vsctl set port s0-eth24 vlan_mode=trunk trunks=%s' % vlans)

        # Router-on-a-Stick subinterfaces
        self.gateway.cmd('ip addr flush dev hq_r-eth0')
        self.gateway.cmd('ip link set hq_r-eth0 up')

        self.gateway.cmd('ip link add link hq_r-eth0 name hq_r-eth0.10 type vlan id 10')
        self.gateway.cmd('ip addr add 10.1.0.1/27 dev hq_r-eth0.10')
        self.gateway.cmd('ip link set up hq_r-eth0.10')

        self.gateway.cmd('ip link add link hq_r-eth0 name hq_r-eth0.20 type vlan id 20')
        self.gateway.cmd('ip addr add 10.1.0.33/27 dev hq_r-eth0.20')
        self.gateway.cmd('ip link set up hq_r-eth0.20')

        self.gateway.cmd('ip link add link hq_r-eth0 name hq_r-eth0.30 type vlan id 30')
        self.gateway.cmd('ip addr add 10.1.0.65/27 dev hq_r-eth0.30')
        self.gateway.cmd('ip link set up hq_r-eth0.30')

        self.gateway.cmd('ip link add link hq_r-eth0 name hq_r-eth0.40 type vlan id 40')
        self.gateway.cmd('ip addr add 10.1.0.97/27 dev hq_r-eth0.40')
        self.gateway.cmd('ip link set up hq_r-eth0.40')

        self.gateway.cmd('ip link add link hq_r-eth0 name hq_r-eth0.50 type vlan id 50')
        self.gateway.cmd('ip addr add 10.1.0.129/27 dev hq_r-eth0.50')
        self.gateway.cmd('ip link set up hq_r-eth0.50')

        self.gateway.cmd('ip link add link hq_r-eth0 name hq_r-eth0.60 type vlan id 60')
        self.gateway.cmd('ip addr add 10.1.0.161/27 dev hq_r-eth0.60')
        self.gateway.cmd('ip link set up hq_r-eth0.60')

        self.gateway.cmd('ip link add link hq_r-eth0 name hq_r-eth0.70 type vlan id 70')
        self.gateway.cmd('ip addr add 10.1.0.193/27 dev hq_r-eth0.70')
        self.gateway.cmd('ip link set up hq_r-eth0.70')

        self.gateway.cmd('ip link add link hq_r-eth0 name hq_r-eth0.80 type vlan id 80')
        self.gateway.cmd('ip addr add 10.1.1.1/27 dev hq_r-eth0.80')
        self.gateway.cmd('ip link set up hq_r-eth0.80')

        self.gateway.cmd('ip link add link hq_r-eth0 name hq_r-eth0.90 type vlan id 90')
        self.gateway.cmd('ip addr add 10.1.1.33/27 dev hq_r-eth0.90')
        self.gateway.cmd('ip link set up hq_r-eth0.90')

        self.gateway.cmd('ip link add link hq_r-eth0 name hq_r-eth0.100 type vlan id 100')
        self.gateway.cmd('ip addr add 10.1.1.65/27 dev hq_r-eth0.100')
