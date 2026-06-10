import os

from router import Router
from switchL3 import SwitchL3


class HQSite:
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
        self.hdns = None
        self.hweb = None
        self.dnsclients = []

    def hqpath(self, filename):
        return os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..', 'hq', filename)
        )

    def build(self, net):
        # HQ router WAN
        self.gateway = net.addHost('hqr', cls=Router, ip=None)

        # Distribution switch
        hdist = net.addSwitch('s0', failMode='standalone')

        # Access switches - one per floor
        hf1 = net.addSwitch('s1', failMode='standalone')
        hf2 = net.addSwitch('s2', failMode='standalone')
        hf3 = net.addSwitch('s3', failMode='standalone')
        hf4 = net.addSwitch('s4', failMode='standalone')

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

        # DNS server for HQ
        self.hdns = net.addHost('hdns', ip=None)
        self.hweb = net.addHost('hweb', ip=None)
        self.dnsclients = [
            hit, hsales, hsec,
            hmgmt, hhr, hfin,
            hinv, hcust, hpurch,
            hcam, hprint, hphone,
            self.hweb,
        ]

        # Host-to-access-switch links
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

        # Access switches to distribution
        net.addLink(hf1, hdist, port1=10, port2=1 )
        net.addLink(hf2, hdist, port1=10, port2=2)
        net.addLink(hf3, hdist, port1=10, port2=3 )
        net.addLink(hf4, hdist, port1=10, port2=4 )

        # Distribution to L3 switch, then L3 switch to WAN router
        net.addLink(hdist, self.mls, port1=24, port2=1, )
        net.addLink(self.mls, self.gateway, port1=2, intfName2='hqr-eth0' )
        net.addLink(self.mls, self.hdns, port1=3, intfName2='hdns-eth0')
        net.addLink(self.mls, self.hweb, port1=4, intfName2='hweb-eth0')

        # Save switches needed later for configure()
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

    def configuredns(self):
        self.mls.cmd('ovs-vsctl set port s5-eth3 tag=10')

        self.hdns.cmd('ip addr flush dev hdns-eth0')
        self.hdns.setIP('10.1.0.10/27', intf='hdns-eth0')
        self.hdns.cmd('ip link set hdns-eth0 up')
        self.hdns.setDefaultRoute('via 10.1.0.1')

        self.hdns.cmd(
            'dnsmasq -d '
            '--conf-file=./hq/site.conf '
            '--pid-file=/tmp/dnsmasq-hq.pid &'
        )

        self.mountresolv()

    def mountresolv(self):
        source = self.hqpath('resolv.conf')

        for host in self.dnsclients:
            host.cmd('umount /etc/resolv.conf 2>/dev/null || true')
            host.cmd('touch /etc/resolv.conf')
            host.cmd(f'mount --bind {source} /etc/resolv.conf')

    def configurehttp(self):
        self.mls.cmd('ovs-vsctl set port s5-eth4 tag=10')

        self.hweb.cmd('ip addr flush dev hweb-eth0')
        self.hweb.setIP('10.1.0.11/27', intf='hweb-eth0')
        self.hweb.cmd('ip link set hweb-eth0 up')
        self.hweb.setDefaultRoute('via 10.1.0.1')

        self.hweb.cmd('mkdir -p /tmp/hq-web')
        self.hweb.cmd(
            "printf '%s\\n' '<h1>MiniHub HQ Web Server</h1>' "
            '> /tmp/hq-web/index.html'
        )
        self.hweb.cmd(
            'cd /tmp/hq-web && '
            'python3 -m http.server 80 '
            '>/tmp/http-hq.log 2>&1 & echo $! > /tmp/http-hq.pid'
        )

    def configure(self):
        allowedvlans = ','.join(str(vlan) for vlan in self.VLANS)

        # Ensure s5 routes between SVIs and transit segments.
        self.mls.cmd('sysctl -w net.ipv4.ip_forward=1')
        self.mls.cmd('sysctl -w net.ipv4.conf.all.rp_filter=0')
        self.mls.cmd('sysctl -w net.ipv4.conf.default.rp_filter=0')
        self.mls.cmd('iptables -P FORWARD ACCEPT')
        self.mls.cmd('iptables -F FORWARD')

        # Access ports - Floor 1
        self.hf1.cmd('ovs-vsctl set port s1-eth1 tag=10')
        self.hf1.cmd('ovs-vsctl set port s1-eth2 tag=20')
        self.hf1.cmd('ovs-vsctl set port s1-eth3 tag=30')
        self.hf1.cmd(f'ovs-vsctl set port s1-eth10 vlan_mode=trunk trunks={allowedvlans}')

        # Access ports - Floor 2
        self.hf2.cmd('ovs-vsctl set port s2-eth1 tag=40')
        self.hf2.cmd('ovs-vsctl set port s2-eth2 tag=50')
        self.hf2.cmd('ovs-vsctl set port s2-eth3 tag=60')
        self.hf2.cmd(f'ovs-vsctl set port s2-eth10 vlan_mode=trunk trunks={allowedvlans}')

        # Access ports - Floor 3
        self.hf3.cmd('ovs-vsctl set port s3-eth1 tag=70')
        self.hf3.cmd('ovs-vsctl set port s3-eth2 tag=80')
        self.hf3.cmd('ovs-vsctl set port s3-eth3 tag=90')
        self.hf3.cmd(f'ovs-vsctl set port s3-eth10 vlan_mode=trunk trunks={allowedvlans}')

        # Access ports - Floor 4
        self.hf4.cmd('ovs-vsctl set port s4-eth1 tag=100')
        self.hf4.cmd('ovs-vsctl set port s4-eth2 tag=110')
        self.hf4.cmd('ovs-vsctl set port s4-eth3 tag=120')
        self.hf4.cmd(f'ovs-vsctl set port s4-eth10 vlan_mode=trunk trunks={allowedvlans}')

        # Distribution trunks
        self.hdist.cmd(f'ovs-vsctl set port s0-eth1 vlan_mode=trunk trunks={allowedvlans}')
        self.hdist.cmd(f'ovs-vsctl set port s0-eth2 vlan_mode=trunk trunks={allowedvlans}')
        self.hdist.cmd(f'ovs-vsctl set port s0-eth3 vlan_mode=trunk trunks={allowedvlans}')
        self.hdist.cmd(f'ovs-vsctl set port s0-eth4 vlan_mode=trunk trunks={allowedvlans}')
        self.hdist.cmd(f'ovs-vsctl set port s0-eth24 vlan_mode=trunk trunks={allowedvlans}')

        # L3 switch trunk toward distribution
        self.mls.cmd(f'ovs-vsctl set port s5-eth1 vlan_mode=trunk trunks={allowedvlans}')

        # Gateways / SVIs on the L3 switch
        for vlanid, gatewaycidr in self.SVIGATEWAYS.items():
            self.createsvi(vlanid, gatewaycidr)

        # Transit link L3 switch -> WAN router.
        # s5-eth2 is an OVS access port; the IP lives on an internal SVI.
        self.mls.cmd(f'ovs-vsctl set port s5-eth2 tag={self.WANVLAN}')
        self.createsvi(self.WANVLAN, '10.1.2.1/30', intfname='hqwan')

        self.gateway.cmd('ip addr flush dev hqr-eth0')
        self.gateway.setIP('10.1.2.2/30', intf='hqr-eth0')
        self.gateway.cmd('ip link set hqr-eth0 up')

        # DNS server in VLAN 10
        self.configuredns()
        self.configurehttp()

        # Routes
        self.mls.cmd('ip route replace default via 10.1.2.2')
        self.gateway.cmd('ip route replace 10.1.0.0/23 via 10.1.2.1')

        return self
