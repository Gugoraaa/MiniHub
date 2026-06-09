from router import Router
from switchL3 import SwitchL3


class Warehouse:
    VLANS = [70, 40, 150, 160, 30, 100, 110, 120]

    def __init__(self, net):
        self.net = net

        # =========================
        # Switches
        # =========================
        self.sw_piso1 = net.addSwitch('s1', failMode='standalone')
        self.sw_piso2 = net.addSwitch('s2', failMode='standalone')

        # Switch capa 3 / multilayer
        self.mls = net.addSwitch('s3', cls=SwitchL3, failMode='standalone')

        # Router de salida WAN / HQ
        self.r_wh = net.addHost('r_wh', cls=Router, ip=None)

        # =========================
        # Hosts representativos
        # =========================
        self.ic1 = net.addHost('ic1', ip='10.4.0.2/27', defaultRoute='via 10.4.0.1')
        self.office1 = net.addHost('office1', ip='10.4.0.34/27', defaultRoute='via 10.4.0.33')
        self.recv1 = net.addHost('recv1', ip='10.4.0.66/27', defaultRoute='via 10.4.0.65')
        self.ship1 = net.addHost('ship1', ip='10.4.0.98/28', defaultRoute='via 10.4.0.97')
        self.sec1 = net.addHost('sec1', ip='10.4.0.114/28', defaultRoute='via 10.4.0.113')
        self.cam1 = net.addHost('camF1', ip='10.4.0.130/28', defaultRoute='via 10.4.0.129')
        self.prt1 = net.addHost('prt1', ip='10.4.0.146/29', defaultRoute='via 10.4.0.145')
        self.phone1 = net.addHost('phone1', ip='10.4.0.154/30', defaultRoute='via 10.4.0.153')
        self.cam2 = net.addHost('camF2', ip='10.4.0.131/28', defaultRoute='via 10.4.0.129')

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
        # Trunks hacia multilayer
        # =========================
        net.addLink(self.sw_piso1, self.mls)      # s1-eth6 <-> s3-eth1
        net.addLink(self.sw_piso2, self.mls)      # s2-eth5 <-> s3-eth2

        # =========================
        # Enlace multilayer -> router
        # =========================
        net.addLink(self.mls, self.r_wh, intfName2='r_wh-eth0')  # s3-eth3 <-> r_wh-eth0

    def create_svi(self, vlan_id, gateway_cidr):
        """
        Crea una SVI en el switch capa 3.

        Ejemplo:
            self.create_svi(70, '10.4.0.1/27')

        Esto crea:
            vlan70 = 10.4.0.1/27

        Esa IP funciona como gateway de la VLAN 70.
        """
        intf_name = f'vlan{vlan_id}'

        self.mls.cmd(
            f'ovs-vsctl --may-exist add-port {self.mls.name} {intf_name} '
            f'tag={vlan_id} -- set interface {intf_name} type=internal'
        )

        self.mls.cmd(f'ip addr flush dev {intf_name}')
        self.mls.cmd(f'ip addr add {gateway_cidr} dev {intf_name}')
        self.mls.cmd(f'ip link set {intf_name} up')

    def configure(self):
        """
        Configura VLANs, trunks, SVIs, enlace MLS-router y rutas.
        Se llama DESPUÉS de net.start().
        """

        allowed_vlans = ','.join(str(vlan) for vlan in self.VLANS)

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
        # Trunks access -> multilayer
        # =========================
        self.sw_piso1.cmd(
            f'ovs-vsctl set port s1-eth6 vlan_mode=trunk trunks={allowed_vlans}'
        )

        self.sw_piso2.cmd(
            f'ovs-vsctl set port s2-eth5 vlan_mode=trunk trunks={allowed_vlans}'
        )

        # =========================
        # Trunks en multilayer
        # =========================
        self.mls.cmd(
            f'ovs-vsctl set port s3-eth1 vlan_mode=trunk trunks={allowed_vlans}'
        )

        self.mls.cmd(
            f'ovs-vsctl set port s3-eth2 vlan_mode=trunk trunks={allowed_vlans}'
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
        # Enlace de tránsito MLS -> Router
        # =========================
        self.mls.cmd('ip addr flush dev s3-eth3')
        self.mls.cmd('ip addr add 10.4.1.253/30 dev s3-eth3')
        self.mls.cmd('ip link set s3-eth3 up')

        self.r_wh.cmd('ip addr flush dev r_wh-eth0')
        self.r_wh.cmd('ip addr add 10.4.1.254/30 dev r_wh-eth0')
        self.r_wh.cmd('ip link set r_wh-eth0 up')

        # =========================
        # Rutas
        # =========================

        # El multilayer manda tráfico externo al router
        self.mls.cmd('ip route replace default via 10.4.1.254')

        # El router sabe regresar al bloque del almacén
        self.r_wh.cmd('ip route replace 10.4.0.0/23 via 10.4.1.253')

        return self