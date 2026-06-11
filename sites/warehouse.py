from router import Router
from switchL3 import SwitchL3
from services.dhcp_server import DHCPServer


class Warehouse:
    VLANS = [70, 40, 150, 160, 30, 100, 110, 120]

    def __init__(self, net):
        self.net = net

        # =========================
        # Switches Warehouse
        # =========================
        self.sw_piso1 = net.addSwitch('s6', failMode='standalone')
        self.sw_piso2 = net.addSwitch('s7', failMode='standalone')

        # Switch de distribución Warehouse
        self.sw_dist = net.addSwitch('s9', failMode='standalone')

        # Switch capa 3 / multilayer Warehouse
        self.mls = net.addSwitch('s8', cls=SwitchL3, failMode='standalone')

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
        net.addLink(self.ic1, self.sw_piso1)      # s6-eth1 -> VLAN 70
        net.addLink(self.ship1, self.sw_piso1)    # s6-eth2 -> VLAN 160
        net.addLink(self.recv1, self.sw_piso1)    # s6-eth3 -> VLAN 150
        net.addLink(self.sec1, self.sw_piso1)     # s6-eth4 -> VLAN 30
        net.addLink(self.cam1, self.sw_piso1)     # s6-eth5 -> VLAN 100

        # =========================
        # Enlaces a switch piso 2
        # =========================
        net.addLink(self.office1, self.sw_piso2)  # s7-eth1 -> VLAN 40
        net.addLink(self.prt1, self.sw_piso2)     # s7-eth2 -> VLAN 110
        net.addLink(self.phone1, self.sw_piso2)   # s7-eth3 -> VLAN 120
        net.addLink(self.cam2, self.sw_piso2)     # s7-eth4 -> VLAN 100

        # =========================
        # Enlaces access -> distribución
        # =========================
        net.addLink(self.sw_piso1, self.sw_dist)  # s6-eth6 <-> s9-eth1
        net.addLink(self.sw_piso2, self.sw_dist)  # s7-eth5 <-> s9-eth2

        # =========================
        # Enlace distribución -> multilayer
        # =========================
        net.addLink(self.sw_dist, self.mls)       # s9-eth3 <-> s8-eth1

        # =========================
        # Enlace multilayer -> router WAN
        # =========================
        net.addLink(
            self.mls,
            self.r_wh,
            intfName2='r_wh-eth0'
        )  # s8-eth2 <-> r_wh-eth0

        # =========================
        # Enlace multilayer -> servidor DHCP
        # =========================
        net.addLink(
            self.mls,
            self.dhcp.host,
            intfName2='dhcp_wh-eth0'
        )  # s8-eth3 <-> dhcp_wh-eth0

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
        # Activar routing en s8
        # =========================
        self.mls.cmd('sysctl -w net.ipv4.ip_forward=1')
        self.mls.cmd('sysctl -w net.ipv4.conf.all.rp_filter=0')
        self.mls.cmd('sysctl -w net.ipv4.conf.default.rp_filter=0')
        self.mls.cmd('iptables -P FORWARD ACCEPT')
        self.mls.cmd('iptables -F FORWARD')

        # =========================
        # Puertos access piso 1
        # =========================
        self.sw_piso1.cmd('ovs-vsctl set port s6-eth1 tag=70')
        self.sw_piso1.cmd('ovs-vsctl set port s6-eth2 tag=160')
        self.sw_piso1.cmd('ovs-vsctl set port s6-eth3 tag=150')
        self.sw_piso1.cmd('ovs-vsctl set port s6-eth4 tag=30')
        self.sw_piso1.cmd('ovs-vsctl set port s6-eth5 tag=100')

        # =========================
        # Puertos access piso 2
        # =========================
        self.sw_piso2.cmd('ovs-vsctl set port s7-eth1 tag=40')
        self.sw_piso2.cmd('ovs-vsctl set port s7-eth2 tag=110')
        self.sw_piso2.cmd('ovs-vsctl set port s7-eth3 tag=120')
        self.sw_piso2.cmd('ovs-vsctl set port s7-eth4 tag=100')

        # =========================
        # Trunks access -> distribución
        # =========================
        self.sw_piso1.cmd(
            f'ovs-vsctl set port s6-eth6 vlan_mode=trunk trunks={allowed_vlans}'
        )

        self.sw_piso2.cmd(
            f'ovs-vsctl set port s7-eth5 vlan_mode=trunk trunks={allowed_vlans}'
        )

        # =========================
        # Trunks en switch de distribución
        # =========================
        self.sw_dist.cmd(
            f'ovs-vsctl set port s9-eth1 vlan_mode=trunk trunks={allowed_vlans}'
        )

        self.sw_dist.cmd(
            f'ovs-vsctl set port s9-eth2 vlan_mode=trunk trunks={allowed_vlans}'
        )

        self.sw_dist.cmd(
            f'ovs-vsctl set port s9-eth3 vlan_mode=trunk trunks={allowed_vlans}'
        )

        # =========================
        # Trunk distribución -> multilayer
        # =========================
        self.mls.cmd(
            f'ovs-vsctl set port s8-eth1 vlan_mode=trunk trunks={allowed_vlans}'
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
        # s8      = 10.4.1.253/30
        # r_wh    = 10.4.1.254/30
        # =========================
        self.mls.cmd('ovs-vsctl set port s8-eth2 tag=999')

        self.mls.cmd(
            f'ovs-vsctl --may-exist add-port {self.mls.name} vlan999 '
            f'tag=999 -- set interface vlan999 type=internal'
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
        # s8       = 192.168.104.254/24
        # dhcp_wh  = 192.168.104.10/24
        # =========================
        self.mls.cmd('ovs-vsctl set port s8-eth3 tag=998')

        self.mls.cmd(
            f'ovs-vsctl --may-exist add-port {self.mls.name} vlan998 '
            f'tag=998 -- set interface vlan998 type=internal'
        )

        self.mls.cmd('ip addr flush dev vlan998')
        self.mls.cmd('ip addr add 192.168.104.254/24 dev vlan998')
        self.mls.cmd('ip link set vlan998 up')

        self.dhcp.host.cmd('ip addr flush dev dhcp_wh-eth0')
        self.dhcp.host.setIP('192.168.104.10/24', intf='dhcp_wh-eth0')
        self.dhcp.host.cmd('ip link set dhcp_wh-eth0 up')
        self.dhcp.host.cmd('ip route replace default via 192.168.104.254')

        # =========================
        # Rutas WAN internas del Warehouse
        # =========================
        self.mls.cmd('ip route replace default via 10.4.1.254')
        self.r_wh.cmd('ip route replace 10.4.0.0/23 via 10.4.1.253')
        self.r_wh.cmd('ip route replace 192.168.104.0/24 via 10.4.1.253')

        # =========================
        # DHCP Server con dnsmasq
        # =========================
        self.dhcp.start()

        # =========================
        # DHCP Relay en s8
        # =========================
        # self.mls.cmd('killall dhcrelay 2>/dev/null || true')

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
        self.mls.cmd('sleep 1')

        self.start_dhcp_clients()
        self.configureclientdns()

        return self

    def configureclientdns(self):
        for host in (
            self.ic1, self.office1, self.recv1, self.ship1,
            self.sec1, self.cam1, self.prt1, self.phone1, self.cam2
        ):
            host.cmd('echo "nameserver 10.1.1.162" > /etc/resolv.conf')

    def start_dhcp_clients(self):
        for host in (
            self.ic1, self.office1, self.recv1, self.ship1,
            self.sec1, self.cam1, self.prt1, self.phone1, self.cam2
        ):
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
        """
        Detiene servicios del Warehouse antes de apagar Mininet.
        """

        # Detener DHCP relay en s8
        self.mls.cmd('killall dhcrelay 2>/dev/null || true')

        # Detener servidor DHCP
        self.dhcp.stop()

        # Detener clientes DHCP en hosts
        self.ic1.cmd('killall dhclient 2>/dev/null || true')
        self.office1.cmd('killall dhclient 2>/dev/null || true')
        self.recv1.cmd('killall dhclient 2>/dev/null || true')
        self.ship1.cmd('killall dhclient 2>/dev/null || true')
        self.sec1.cmd('killall dhclient 2>/dev/null || true')
        self.cam1.cmd('killall dhclient 2>/dev/null || true')
        self.prt1.cmd('killall dhclient 2>/dev/null || true')
        self.phone1.cmd('killall dhclient 2>/dev/null || true')
        self.cam2.cmd('killall dhclient 2>/dev/null || true')