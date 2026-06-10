from router import Router
from switchL3 import SwitchL3
from services.dhcp_server import DHCPServer

class TiendaSanPedro:
    VLANS = [30, 40, 100, 110, 120, 130, 140]
    DHCP_VLAN = 998
    TRANSIT_VLAN = 999

    SP_DHCP_HOSTS = (
        'sp_hwifi',
        'sp_hchk',
        'sp_hsec',
        'sp_hadmin',
        'sp_hcam',
        'sp_hprint',
        'sp_hphone',
    )

    def __init__(self):
        self.gateway = None

    def build(self, net):
        # Router
        self.gateway = net.addHost('sp_r', cls=Router, ip=None)

        #Core switch 1
        s17 = net.addSwitch('s17', failMode='standalone')

        # Core switch
        s16 = net.addSwitch('s16', cls=SwitchL3, failMode='standalone')

        # Access switches
        s13 = net.addSwitch('s13', failMode='standalone')
        s14 = net.addSwitch('s14', failMode='standalone')
        s15 = net.addSwitch('s15', failMode='standalone')

        self.dhcp = DHCPServer(
            net=net,
            name='dhcp_sp',
            ip_cidr='192.168.105.10/24',
            gateway='192.168.105.254',
            conf_path='tmp/dhcp_sanpedro.conf',
            pid_path='tmp/dhcp_sanpedro.pid',
            lease_path='tmp/dhcp_sanpedro.leases',
            log_path='tmp/dhcp_sanpedro.log'
        )

        # Hosts por VLAN (IP por DHCP)
        self.sp_hwifi = net.addHost('sp_hwifi', ip=None)
        self.sp_hchk = net.addHost('sp_hchk', ip=None)
        self.sp_hsec = net.addHost('sp_hsec', ip=None)
        self.sp_hadmin = net.addHost('sp_hadmin', ip=None)
        self.sp_hcam = net.addHost('sp_hcam', ip=None)
        self.sp_hprint = net.addHost('sp_hprint', ip=None)
        self.sp_hphone = net.addHost('sp_hphone', ip=None)

        # Host → access switch
        net.addLink(self.sp_hchk, s13, port2=1)
        net.addLink(self.sp_hsec, s13, port2=2)
        net.addLink(self.sp_hprint, s13, port2=3)

        net.addLink(self.sp_hwifi, s14, port2=1)
        net.addLink(self.sp_hcam, s14, port2=2)

        net.addLink(self.sp_hadmin, s15, port2=1)
        net.addLink(self.sp_hphone, s15, port2=2)

        # Access switches → core (trunk)
        net.addLink(s13, s16, port1=10, port2=1, bw=1000)
        net.addLink(s14, s16, port1=10, port2=2, bw=1000)
        net.addLink(s15, s16, port1=10, port2=3, bw=1000)

        # Core → servidor DHCP
        net.addLink(s16, self.dhcp.host, port1=4, intfName2='dhcp_sp-eth0', bw=1000)

        # Core → router
        net.addLink(s16, self.gateway, port1=24, intfName2='sp_r-eth0', bw=1000)

        # Save references needed by configure()
        self.s16 = s16
        self.s13 = s13
        self.s14 = s14
        self.s15 = s15

    def create_svi(self, vlan_id, gateway_cidr):
        intf_name = f'sp_vlan{vlan_id}'

        self.s16.cmd(
            f'ovs-vsctl --may-exist add-port {self.s16.name} {intf_name} '
            f'tag={vlan_id} -- set interface {intf_name} type=internal'
        )

        self.s16.cmd(f'ip addr flush dev {intf_name}')
        self.s16.cmd(f'ip addr add {gateway_cidr} dev {intf_name}')
        self.s16.cmd(f'ip link set {intf_name} up')

    def stop_services(self):
        self.s16.cmd('killall dhcrelay 2>/dev/null || true')
        self.dhcp.stop()

        for host_name in self.SP_DHCP_HOSTS:
            getattr(self, host_name).cmd('killall dhclient 2>/dev/null || true')

    def configure(self):
        vlans = ','.join(str(vlan) for vlan in self.VLANS)

        # --- Access ports: s13 — Checkout, Security, Impresoras ---
        self.s13.cmd('ovs-vsctl set port s13-eth1  tag=140')   # Checkout
        self.s13.cmd('ovs-vsctl set port s13-eth2  tag=30')    # Security
        self.s13.cmd('ovs-vsctl set port s13-eth3  tag=110')   # Impresoras
        self.s13.cmd('ovs-vsctl set port s13-eth10 vlan_mode=trunk trunks=%s' % vlans)

        # --- Access ports: s14 — WiFi, Cámaras ---
        self.s14.cmd('ovs-vsctl set port s14-eth1  tag=130')   # WiFi
        self.s14.cmd('ovs-vsctl set port s14-eth2  tag=100')   # Cámaras
        self.s14.cmd('ovs-vsctl set port s14-eth10 vlan_mode=trunk trunks=%s' % vlans)

        # --- Access ports: s15 — Admin, Teléfonos ---
        self.s15.cmd('ovs-vsctl set port s15-eth1  tag=40')    # Admin
        self.s15.cmd('ovs-vsctl set port s15-eth2  tag=120')   # Teléfonos
        self.s15.cmd('ovs-vsctl set port s15-eth10 vlan_mode=trunk trunks=%s' % vlans)

        # --- Core switch trunks (access switches) ---
        self.s16.cmd('ovs-vsctl set port s16-eth1 vlan_mode=trunk trunks=%s' % vlans)
        self.s16.cmd('ovs-vsctl set port s16-eth2 vlan_mode=trunk trunks=%s' % vlans)
        self.s16.cmd('ovs-vsctl set port s16-eth3 vlan_mode=trunk trunks=%s' % vlans)
        self.s16.cmd('ovs-vsctl set port s16-eth4 tag=%d' % self.DHCP_VLAN)

        # --- Gateways / SVIs en el core L3 (s16) ---
        self.create_svi(130, '10.3.0.1/24')     # WiFi Invitados/Clientes
        self.create_svi(140, '10.3.1.1/27')     # Cajas / Checkout
        self.create_svi(40,  '10.3.1.33/29')    # Oficina Administrativa
        self.create_svi(30,  '10.3.1.41/29')    # Security
        self.create_svi(100, '10.3.1.49/25')    # Cámaras
        self.create_svi(110, '10.3.1.113/28')   # Impresoras
        self.create_svi(120, '10.3.1.129/29')    # Teléfonos

        # --- Enlace core ↔ servidor DHCP (VLAN 998) ---
        self.create_svi(self.DHCP_VLAN, '192.168.105.254/24')

        self.dhcp.host.cmd('ip addr flush dev dhcp_sp-eth0')
        self.dhcp.host.setIP('192.168.105.10/24', intf='dhcp_sp-eth0')
        self.dhcp.host.cmd('ip link set dhcp_sp-eth0 up')
        self.dhcp.host.cmd('ip route replace default via 192.168.105.254')

        # --- Transit link: core (eth24) ↔ router (eth0) via VLAN 999 ---
        self.s16.cmd('ovs-vsctl set port s16-eth24 tag=%d' % self.TRANSIT_VLAN)
        self.create_svi(self.TRANSIT_VLAN, '10.3.255.253/30')

        self.gateway.cmd('ip addr flush dev sp_r-eth0')
        self.gateway.cmd('ip addr add 10.3.255.254/30 dev sp_r-eth0')
        self.gateway.cmd('ip link set sp_r-eth0 up')

        # --- Routing ---
        self.s16.cmd('ip route replace default via 10.3.255.254')
        self.gateway.cmd('ip route replace 10.3.0.0/23 via 10.3.255.253')
        self.gateway.cmd('ip route replace 192.168.105.0/24 via 10.3.255.253')

        # --- DHCP server + relay ---
        self.dhcp.start()

        self.s16.cmd(
            'dhcrelay -4 '
            '-i sp_vlan130 '
            '-i sp_vlan140 '
            '-i sp_vlan40 '
            '-i sp_vlan30 '
            '-i sp_vlan100 '
            '-i sp_vlan110 '
            '-i sp_vlan120 '
            '-i sp_vlan998 '
            '192.168.105.10'
        )
