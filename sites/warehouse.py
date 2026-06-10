from router import Router
from switchL3 import SwitchL3
from services.dhcp_server import DHCPServer


class Warehouse:
    VLANS = [70, 40, 150, 160, 30, 100, 110, 120]

    def __init__(self, net):
        self.net = net

        # =========================
        # Switches
        # =========================
        self.sw_piso1 = net.addSwitch('s1', failMode='standalone')
        self.sw_piso2 = net.addSwitch('s2', failMode='standalone')

        # Switch de distribución
        self.sw_dist = net.addSwitch('s4', failMode='standalone')

        # Switch capa 3 / multilayer
        self.mls = net.addSwitch('s3', cls=SwitchL3, failMode='standalone')

        # Router de salida WAN / HQ
        self.r_wh = net.addHost('r_wh', cls=Router, ip=None)

        # =========================
        # Servidor DHCP Warehouse
        # =========================
        self.dhcp = DHCPServer(
            net=net,
            name='dhcp_wh',
            ip_cidr='192.168.104.10/24',
            gateway='192.168.104.254',
            conf_path='tmp/dhcp_warehouse.conf',
            pid_path='tmp/dhcp_warehouse.pid',
            lease_path='tmp/dhcp_warehouse.leases',
            log_path='tmp/dhcp_warehouse.log'
        )

        # =========================
        # Hosts representativos por DHCP
        # =========================
        self.ic1 = net.addHost('ic1', ip=None)
        self.office1 = net.addHost('office1', ip=None)
        self.recv1 = net.addHost('recv1', ip=None)
        self.ship1 = net.addHost('ship1', ip=None)
        self.sec1 = net.addHost('sec1', ip=None)
        self.cam1 = net.addHost('camF1', ip=None)
        self.prt1 = net.addHost('prt1', ip=None)
        self.phone1 = net.addHost('phone1', ip=None)
        self.cam2 = net.addHost('camF2', ip=None)

        # =========================
        # Enlaces a switch piso 1
        # =========================
        net.addLink(self.ic1, self.sw_piso1)      # s1-eth1 -> VLAN 70
        net.addLink(self.ship1, self.sw_piso1)    # s1-eth2 -> VLAN 160
        net.addLink(self.recv1, self.sw_piso1)    # s1-eth3 -> VLAN 150
        net.addLink(self.sec1, self.sw_piso1)     # s1-eth4 -> VLAN 30
        net.addLink(self.cam1, self.sw_piso1)     # s1-eth5 -> VLAN 100

        # =========================
        # Enlaces a switch piso 2
        # =========================
        net.addLink(self.office1, self.sw_piso2)  # s2-eth1 -> VLAN 40
        net.addLink(self.prt1, self.sw_piso2)     # s2-eth2 -> VLAN 110
        net.addLink(self.phone1, self.sw_piso2)   # s2-eth3 -> VLAN 120
        net.addLink(self.cam2, self.sw_piso2)     # s2-eth4 -> VLAN 100

        # =========================
        # Enlaces access -> distribución
        # =========================
        net.addLink(self.sw_piso1, self.sw_dist)  # s1-eth6 <-> s4-eth1
        net.addLink(self.sw_piso2, self.sw_dist)  # s2-eth5 <-> s4-eth2

        # =========================
        # Enlace distribución -> multilayer
        # =========================
        net.addLink(self.sw_dist, self.mls)       # s4-eth3 <-> s3-eth1

        # =========================
        # Enlace multilayer -> router WAN
        # =========================
        net.addLink(
            self.mls,
            self.r_wh,
            intfName2='r_wh-eth0'
        )  # s3-eth2 <-> r_wh-eth0

        # =========================
        # Enlace multilayer -> servidor DHCP
        # =========================
        net.addLink(
            self.mls,
            self.dhcp.host,
            intfName2='dhcp_wh-eth0'
        )  # s3-eth3 <-> dhcp_wh-eth0

    def create_svi(self, vlan_id, gateway_cidr):
        intf_name = f'vlan{vlan_id}'

        self.mls.cmd(
            f'ovs-vsctl --may-exist add-port {self.mls.name} {intf_name} '
            f'tag={vlan_id} -- set interface {intf_name} type=internal'
        )

        self.mls.cmd(f'ip addr flush dev {intf_name}')
        self.mls.cmd(f'ip addr add {gateway_cidr} dev {intf_name}')
        self.mls.cmd(f'ip link set {intf_name} up')

    def configure(self):
        allowed_vlans = ','.join(str(vlan) for vlan in self.VLANS)

        # =========================
        # Activar routing en s3
        # =========================
        self.mls.cmd('sysctl -w net.ipv4.ip_forward=1')
        self.mls.cmd('sysctl -w net.ipv4.conf.all.rp_filter=0')
        self.mls.cmd('sysctl -w net.ipv4.conf.default.rp_filter=0')
        self.mls.cmd('iptables -P FORWARD ACCEPT')
        self.mls.cmd('iptables -F FORWARD')

        # =========================
        # Puertos access piso 1
        # =========================
        self.sw_piso1.cmd('ovs-vsctl set port s1-eth1 tag=70')
        self.sw_piso1.cmd('ovs-vsctl set port s1-eth2 tag=160')
        self.sw_piso1.cmd('ovs-vsctl set port s1-eth3 tag=150')
        self.sw_piso1.cmd('ovs-vsctl set port s1-eth4 tag=30')
        self.sw_piso1.cmd('ovs-vsctl set port s1-eth5 tag=100')

        # =========================
        # Puertos access piso 2
        # =========================
        self.sw_piso2.cmd('ovs-vsctl set port s2-eth1 tag=40')
        self.sw_piso2.cmd('ovs-vsctl set port s2-eth2 tag=110')
        self.sw_piso2.cmd('ovs-vsctl set port s2-eth3 tag=120')
        self.sw_piso2.cmd('ovs-vsctl set port s2-eth4 tag=100')

        # =========================
        # Trunks access -> distribución
        # =========================
        self.sw_piso1.cmd(
            f'ovs-vsctl set port s1-eth6 vlan_mode=trunk trunks={allowed_vlans}'
        )

        self.sw_piso2.cmd(
            f'ovs-vsctl set port s2-eth5 vlan_mode=trunk trunks={allowed_vlans}'
        )

        # =========================
        # Trunks en switch de distribución
        # =========================
        self.sw_dist.cmd(
            f'ovs-vsctl set port s4-eth1 vlan_mode=trunk trunks={allowed_vlans}'
        )

        self.sw_dist.cmd(
            f'ovs-vsctl set port s4-eth2 vlan_mode=trunk trunks={allowed_vlans}'
        )

        self.sw_dist.cmd(
            f'ovs-vsctl set port s4-eth3 vlan_mode=trunk trunks={allowed_vlans}'
        )

        # =========================
        # Trunk distribución -> multilayer
        # =========================
        self.mls.cmd(
            f'ovs-vsctl set port s3-eth1 vlan_mode=trunk trunks={allowed_vlans}'
        )

        # =========================
        # Gateways / SVIs en el multilayer
        # =========================
        self.create_svi(70, '10.4.0.1/27')
        self.create_svi(40, '10.4.0.33/27')
        self.create_svi(150, '10.4.0.65/27')
        self.create_svi(160, '10.4.0.97/28')
        self.create_svi(30, '10.4.0.113/28')
        self.create_svi(100, '10.4.0.129/28')
        self.create_svi(110, '10.4.0.145/29')
        self.create_svi(120, '10.4.0.153/30')

        # =========================
        # Enlace MLS -> Router WAN
        # VLAN 999:
        # s3      = 10.4.1.253/30
        # r_wh    = 10.4.1.254/30
        # =========================
        self.mls.cmd('ovs-vsctl set port s3-eth2 tag=999')

        self.mls.cmd(
            'ovs-vsctl --may-exist add-port s3 vlan999 '
            'tag=999 -- set interface vlan999 type=internal'
        )

        self.mls.cmd('ip addr flush dev vlan999')
        self.mls.cmd('ip addr add 10.4.1.253/30 dev vlan999')
        self.mls.cmd('ip link set vlan999 up')

        self.r_wh.cmd('ip addr flush dev r_wh-eth0')
        self.r_wh.setIP('10.4.1.254/30', intf='r_wh-eth0')
        self.r_wh.cmd('ip link set r_wh-eth0 up')

        # =========================
        # Enlace MLS -> DHCP Server
        # VLAN 998:
        # s3       = 192.168.104.254/24
        # dhcp_wh  = 192.168.104.10/24
        # =========================
        self.mls.cmd('ovs-vsctl set port s3-eth3 tag=998')

        self.mls.cmd(
            'ovs-vsctl --may-exist add-port s3 vlan998 '
            'tag=998 -- set interface vlan998 type=internal'
        )

        self.mls.cmd('ip addr flush dev vlan998')
        self.mls.cmd('ip addr add 192.168.104.254/24 dev vlan998')
        self.mls.cmd('ip link set vlan998 up')

        self.dhcp.host.cmd('ip addr flush dev dhcp_wh-eth0')
        self.dhcp.host.setIP('192.168.104.10/24', intf='dhcp_wh-eth0')
        self.dhcp.host.cmd('ip link set dhcp_wh-eth0 up')
        self.dhcp.host.cmd('ip route replace default via 192.168.104.254')

        # =========================
        # Rutas WAN
        # =========================
        self.mls.cmd('ip route replace default via 10.4.1.254')
        self.r_wh.cmd('ip route replace 10.4.0.0/23 via 10.4.1.253')
        self.r_wh.cmd('ip route replace 192.168.104.0/24 via 10.4.1.253')

        # =========================
        # DHCP Server con dnsmasq
        # =========================
        self.dhcp.start()

        # =========================
        # DHCP Relay en s3
        # =========================
        self.mls.cmd('killall dhcrelay 2>/dev/null || true')

        self.mls.cmd(
            'dhcrelay -4 '
            '-i vlan70 '
            '-i vlan40 '
            '-i vlan150 '
            '-i vlan160 '
            '-i vlan30 '
            '-i vlan100 '
            '-i vlan110 '
            '-i vlan120 '
            '-i vlan998 '
            '192.168.104.10'
        )

        return self
    