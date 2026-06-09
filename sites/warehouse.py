from mininet.net import Mininet
from mininet.node import OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel
from router import Router
from svi import create_svi

VLANS = [70, 40, 150, 160, 30, 100, 110, 120]




def create_topology():
    net = Mininet(controller=None, switch=OVSSwitch, link=TCLink)

    # Switches de acceso
    sw_piso1 = net.addSwitch('sw_piso1', failMode='standalone')
    sw_piso2 = net.addSwitch('sw_piso2', failMode='standalone')

    # Switch capa 3 / multilayer
    mls = net.addSwitch('mls', failMode='standalone')

    # Router de salida WAN / HQ
    r_wh = net.addHost('r_wh', cls=Router, ip=None)

    # Hosts representativos por VLAN
    ic1 = net.addHost('ic1', ip='10.4.0.2/27', defaultRoute='via 10.4.0.1')
    office1 = net.addHost('office1', ip='10.4.0.34/27', defaultRoute='via 10.4.0.33')
    recv1 = net.addHost('recv1', ip='10.4.0.66/27', defaultRoute='via 10.4.0.65')
    ship1 = net.addHost('ship1', ip='10.4.0.98/28', defaultRoute='via 10.4.0.97')
    sec1 = net.addHost('sec1', ip='10.4.0.114/28', defaultRoute='via 10.4.0.113')
    cam1 = net.addHost('camF1', ip='10.4.0.130/28', defaultRoute='via 10.4.0.129')
    prt1 = net.addHost('prt1', ip='10.4.0.146/29', defaultRoute='via 10.4.0.145')
    phone1 = net.addHost('phone1', ip='10.4.0.154/30', defaultRoute='via 10.4.0.153')
    cam2 = net.addHost('camF2', ip='10.4.0.131/28', defaultRoute='via 10.4.0.129')

    # Hosts al switch piso 1
    net.addLink(ic1, sw_piso1)      # sw_piso1-eth1 -> VLAN 70
    net.addLink(ship1, sw_piso1)    # sw_piso1-eth2 -> VLAN 160
    net.addLink(recv1, sw_piso1)    # sw_piso1-eth3 -> VLAN 150
    net.addLink(sec1, sw_piso1)     # sw_piso1-eth4 -> VLAN 30
    net.addLink(cam1, sw_piso1)     # sw_piso1-eth5 -> VLAN 100

    # Hosts al switch piso 2
    net.addLink(office1, sw_piso2)  # sw_piso2-eth1 -> VLAN 40
    net.addLink(prt1, sw_piso2)     # sw_piso2-eth2 -> VLAN 110
    net.addLink(phone1, sw_piso2)   # sw_piso2-eth3 -> VLAN 120
    net.addLink(cam2, sw_piso2)     # sw_piso2-eth4 -> VLAN 100

    # Trunks hacia multilayer
    net.addLink(sw_piso1, mls)      # sw_piso1-eth6 <-> mls-eth1
    net.addLink(sw_piso2, mls)      # sw_piso2-eth5 <-> mls-eth2

    # Enlace multilayer switch -> router
    net.addLink(mls, r_wh, intfName2='r_wh-eth0')  # mls-eth3 <-> r_wh-eth0

    net.start()

    # Activar routing en el multilayer switch
    mls.cmd('sysctl -w net.ipv4.ip_forward=1')

    # Configurar puertos access en switch piso 1
    sw_piso1.cmd('ovs-vsctl set port sw_piso1-eth1 tag=70')
    sw_piso1.cmd('ovs-vsctl set port sw_piso1-eth2 tag=160')
    sw_piso1.cmd('ovs-vsctl set port sw_piso1-eth3 tag=150')
    sw_piso1.cmd('ovs-vsctl set port sw_piso1-eth4 tag=30')
    sw_piso1.cmd('ovs-vsctl set port sw_piso1-eth5 tag=100')

    # Configurar puertos access en switch piso 2
    sw_piso2.cmd('ovs-vsctl set port sw_piso2-eth1 tag=40')
    sw_piso2.cmd('ovs-vsctl set port sw_piso2-eth2 tag=110')
    sw_piso2.cmd('ovs-vsctl set port sw_piso2-eth3 tag=120')
    sw_piso2.cmd('ovs-vsctl set port sw_piso2-eth4 tag=100')

    # Configurar trunks en los switches de acceso
    allowed_vlans = ','.join(str(vlan) for vlan in VLANS)

    sw_piso1.cmd(f'ovs-vsctl set port sw_piso1-eth6 trunks={allowed_vlans}')
    sw_piso2.cmd(f'ovs-vsctl set port sw_piso2-eth5 trunks={allowed_vlans}')

    # Configurar trunks en el multilayer switch
    mls.cmd(f'ovs-vsctl set port mls-eth1 trunks={allowed_vlans}')
    mls.cmd(f'ovs-vsctl set port mls-eth2 trunks={allowed_vlans}')

    # Crear gateways/SVIs en el multilayer
    create_svi(mls, 70, '10.4.0.1/27')
    create_svi(mls, 40, '10.4.0.33/27')
    create_svi(mls, 150, '10.4.0.65/27')
    create_svi(mls, 160, '10.4.0.97/28')
    create_svi(mls, 30, '10.4.0.113/28')
    create_svi(mls, 100, '10.4.0.129/28')
    create_svi(mls, 110, '10.4.0.145/29')
    create_svi(mls, 120, '10.4.0.153/30')

    # Configurar enlace de tránsito entre multilayer y router
    # Red de tránsito: 10.4.1.252/30
    # mls: 10.4.1.253
    # router: 10.4.1.254

    mls.cmd('ip addr flush dev mls-eth3')
    mls.cmd('ip addr add 10.4.1.253/30 dev mls-eth3')
    mls.cmd('ip link set mls-eth3 up')

    r_wh.cmd('ip addr flush dev r_wh-eth0')
    r_wh.cmd('ip addr add 10.4.1.254/30 dev r_wh-eth0')
    r_wh.cmd('ip link set r_wh-eth0 up')

    # Rutas entre multilayer y router
    # El multilayer manda tráfico desconocido al router
    mls.cmd('ip route replace default via 10.4.1.254')

    # El router sabe regresar a todas las redes del almacén
    r_wh.cmd('ip route replace 10.4.0.0/23 via 10.4.1.253')

    CLI(net)

    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    create_topology()