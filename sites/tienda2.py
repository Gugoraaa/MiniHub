from mininet.net import Mininet
from mininet.node import OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel

from router import Router
from switchL3 import SwitchL3


class Tienda2:
    VLANS = [130, 140, 40, 30, 100, 110, 120]

    def __init__(self, net):
        self.net = net

        # Switches
        self.s1 = net.addSwitch('s2f1', failMode='standalone')   # Piso 1
        self.s2 = net.addSwitch('s2f2', failMode='standalone')   # Piso 2
        self.mls = net.addSwitch('s2c', cls=SwitchL3, failMode='standalone')
        self.r = net.addHost('r_t2', cls=Router, ip=None)

        # Checkout, Security y Shelfs -> switch piso 1
        self.checkout = net.addHost('checkout', ip='10.3.1.10/27', defaultRoute='via 10.3.1.1')
        self.tprt = net.addHost('tprt', ip='10.3.1.82/29', defaultRoute='via 10.3.1.81')
        self.cam_ck = net.addHost('cam_ck', ip='10.3.1.66/28', defaultRoute='via 10.3.1.65')
        self.ap_sec = net.addHost('ap_sec', ip='10.3.0.10/24', defaultRoute='via 10.3.0.1')
        self.alarm = net.addHost('alarm', ip='10.3.1.50/28', defaultRoute='via 10.3.1.49')
        self.cam_se = net.addHost('cam_se', ip='10.3.1.67/28', defaultRoute='via 10.3.1.65')
        self.ap_sh = net.addHost('ap_sh', ip='10.3.0.11/24', defaultRoute='via 10.3.0.1')
        self.cam_sh = net.addHost('cam_sh', ip='10.3.1.68/28', defaultRoute='via 10.3.1.65')

        net.addLink(self.checkout, self.s1)   # s2f1-eth1 VLAN 140
        net.addLink(self.tprt, self.s1)       # s2f1-eth2 VLAN 110
        net.addLink(self.cam_ck, self.s1)     # s2f1-eth3 VLAN 100
        net.addLink(self.ap_sec, self.s1)     # s2f1-eth4 VLAN 130
        net.addLink(self.alarm, self.s1)      # s2f1-eth5 VLAN 30
        net.addLink(self.cam_se, self.s1)     # s2f1-eth6 VLAN 100
        net.addLink(self.ap_sh, self.s1)      # s2f1-eth7 VLAN 130
        net.addLink(self.cam_sh, self.s1)     # s2f1-eth8 VLAN 100
        net.addLink(self.s1, self.mls)        # s2f1-eth9 <-> s2c-eth1

        # Oficina administrativa -> switch piso 2
        self.pc_admin = net.addHost('pc_admin', ip='10.3.1.34/28', defaultRoute='via 10.3.1.33')
        self.phone = net.addHost('phone', ip='10.3.1.90/30', defaultRoute='via 10.3.1.89')
        self.adprt = net.addHost('adprt', ip='10.3.1.83/29', defaultRoute='via 10.3.1.81')
        self.cam_ad = net.addHost('cam_ad', ip='10.3.1.69/28', defaultRoute='via 10.3.1.65')

        net.addLink(self.pc_admin, self.s2)   # s2f2-eth1 VLAN 40
        net.addLink(self.phone, self.s2)      # s2f2-eth2 VLAN 120
        net.addLink(self.adprt, self.s2)      # s2f2-eth3 VLAN 110
        net.addLink(self.cam_ad, self.s2)     # s2f2-eth4 VLAN 100
        net.addLink(self.s2, self.mls)        # s2f2-eth5 <-> s2c-eth2

        # Servidor DHCP y salida hacia router
        self.dhcp_srv = net.addHost('dhcp_srv', ip='10.3.1.35/28', defaultRoute='via 10.3.1.33')
        net.addLink(self.dhcp_srv, self.mls)  # s2c-eth3 VLAN 40
        net.addLink(self.mls, self.r, intfName2='r_t2-wan')  # s2c-eth4

    def create_svi(self, vlan_id, gateway_cidr):
        intf = f'vlan{vlan_id}'
        self.mls.cmd(
            f'ovs-vsctl --may-exist add-port {self.mls.name} {intf} '
            f'tag={vlan_id} -- set interface {intf} type=internal'
        )
        self.mls.cmd(f'ip addr flush dev {intf}')
        self.mls.cmd(f'ip addr add {gateway_cidr} dev {intf}')
        self.mls.cmd(f'ip link set {intf} up')

    def configure(self):
        allowed = ','.join(str(vlan) for vlan in self.VLANS)

        # Puertos access piso 1
        self.s1.cmd('ovs-vsctl set port s2f1-eth1 tag=140')  # checkout
        self.s1.cmd('ovs-vsctl set port s2f1-eth2 tag=110')  # impresoras ticket
        self.s1.cmd('ovs-vsctl set port s2f1-eth3 tag=100')  # camaras checkout
        self.s1.cmd('ovs-vsctl set port s2f1-eth4 tag=130')  # AP security
        self.s1.cmd('ovs-vsctl set port s2f1-eth5 tag=30')   # alarmas
        self.s1.cmd('ovs-vsctl set port s2f1-eth6 tag=100')  # camaras security
        self.s1.cmd('ovs-vsctl set port s2f1-eth7 tag=130')  # AP shelfs
        self.s1.cmd('ovs-vsctl set port s2f1-eth8 tag=100')  # camaras shelfs
        self.s1.cmd(f'ovs-vsctl set port s2f1-eth9 vlan_mode=trunk trunks={allowed}')

        # Puertos access piso 2
        self.s2.cmd('ovs-vsctl set port s2f2-eth1 tag=40')   # PCs admin
        self.s2.cmd('ovs-vsctl set port s2f2-eth2 tag=120')  # telefono
        self.s2.cmd('ovs-vsctl set port s2f2-eth3 tag=110')  # impresora admin
        self.s2.cmd('ovs-vsctl set port s2f2-eth4 tag=100')  # camaras admin
        self.s2.cmd(f'ovs-vsctl set port s2f2-eth5 vlan_mode=trunk trunks={allowed}')

        # Trunks y access directos en multilayer
        self.mls.cmd(f'ovs-vsctl set port s2c-eth1 vlan_mode=trunk trunks={allowed}')
        self.mls.cmd(f'ovs-vsctl set port s2c-eth2 vlan_mode=trunk trunks={allowed}')
        self.mls.cmd('ovs-vsctl set port s2c-eth3 tag=40')   # DHCP server

        # Gateways de VLAN en el switch multilayer
        self.create_svi(130, '10.3.0.1/24')    # Access points
        self.create_svi(140, '10.3.1.1/27')    # Checkout
        self.create_svi(40, '10.3.1.33/28')    # Admin / DHCP
        self.create_svi(30, '10.3.1.49/28')    # Alarmas
        self.create_svi(100, '10.3.1.65/28')   # Camaras
        self.create_svi(110, '10.3.1.81/29')   # Impresoras
        self.create_svi(120, '10.3.1.89/30')   # Telefonos

        # Enlace multilayer -> router
        self.mls.cmd('ip addr flush dev s2c-eth4')
        self.mls.cmd('ip addr add 10.3.1.249/30 dev s2c-eth4')
        self.mls.cmd('ip link set s2c-eth4 up')

        self.r.cmd('ip addr flush dev r_t2-wan')
        self.r.cmd('ip addr add 10.3.1.250/30 dev r_t2-wan')
        self.r.cmd('ip link set r_t2-wan up')

        self.mls.cmd('ip route replace default via 10.3.1.250')
        self.r.cmd('ip route replace 10.3.0.0/23 via 10.3.1.249')

        return self


def run():
    net = Mininet(
        controller=None,
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True,
        autoStaticArp=False,
    )

    t2 = Tienda2(net)
    net.start()
    t2.configure()

    print('\n=== Tienda 2 topology loaded ===')
    print('Pruebas sugeridas dentro de Mininet:')
    print('  checkout ping -c 3 10.3.1.1')
    print('  checkout ping -c 3 pc_admin')
    print('  ap_sec ping -c 3 ap_sh')
    print('  cam_ck ping -c 3 cam_ad')
    print('  dhcp_srv ping -c 3 pc_admin')
    print('================================\n')

    CLI(net)
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    run()
