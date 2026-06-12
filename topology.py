from mininet.net import Mininet
from mininet.node import OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel

from sites.warehouse import Warehouse
from sites.hq import HQSite
from sites.tienda2 import Tienda2
from sites.tiendaSanPedro import TiendaSanPedro

from validate_network import run_validation


def run():
    net = Mininet(
        controller=None,
        switch=OVSSwitch,
        autoSetMacs=True,
        autoStaticArp=False
    )

    hq = HQSite()
    wh = Warehouse(net)
    t2 = Tienda2(net)
    sp = TiendaSanPedro()

    hq.build(net)
    sp.build(net)

    net.addLink(
        wh.r_wh,
        hq.gateway,
        intfName1='r_wh-eth1',
        intfName2='hqr-eth1'
    )


    net.addLink(
        t2.r,
        hq.gateway,
        intfName1='r_t2-eth1',
        intfName2='hqr-eth2'
    )

    net.addLink(
        sp.gateway,
        hq.gateway,
        intfName1='sp_r-eth1',
        intfName2='hqr-eth3'
    )


    net.start()

    hq.configure()
    wh.configure()
    t2.configure()
    sp.configure()

    hq.gateway.cmd('ip addr flush dev hqr-eth1')
    hq.gateway.setIP('10.0.3.1/30', intf='hqr-eth1')
    hq.gateway.cmd('ip link set hqr-eth1 up')

    wh.r_wh.cmd('ip addr flush dev r_wh-eth1')
    wh.r_wh.setIP('10.0.3.2/30', intf='r_wh-eth1')
    wh.r_wh.cmd('ip link set r_wh-eth1 up')


    wh.r_wh.cmd('ip route replace 10.1.0.0/23 via 10.0.3.1')
    wh.r_wh.cmd('ip route replace default via 10.0.3.1')


    hq.gateway.cmd('ip route replace 10.4.0.0/23 via 10.0.3.2')
    hq.gateway.cmd('ip route replace 192.168.104.0/24 via 10.0.3.2')


    hq.gateway.cmd('ip addr flush dev hqr-eth2')
    hq.gateway.setIP('10.0.4.1/30', intf='hqr-eth2')
    hq.gateway.cmd('ip link set hqr-eth2 up')

    t2.r.cmd('ip addr flush dev r_t2-eth1')
    t2.r.setIP('10.0.4.2/30', intf='r_t2-eth1')
    t2.r.cmd('ip link set r_t2-eth1 up')


    t2.r.cmd('ip route replace 10.1.0.0/23 via 10.0.4.1')
    t2.r.cmd('ip route replace default via 10.0.4.1')


    hq.gateway.cmd('ip route replace 10.3.0.0/23 via 10.0.4.2')
    hq.gateway.cmd('ip route replace 192.168.103.0/24 via 10.0.4.2')




    hq.gateway.cmd('ip addr flush dev hqr-eth3')
    hq.gateway.setIP('10.0.5.1/30', intf='hqr-eth3')
    hq.gateway.cmd('ip link set hqr-eth3 up')

    sp.gateway.cmd('ip addr flush dev sp_r-eth1')
    sp.gateway.setIP('10.0.5.2/30', intf='sp_r-eth1')
    sp.gateway.cmd('ip link set sp_r-eth1 up')


    sp.gateway.cmd('ip route replace 10.1.0.0/23 via 10.0.5.1')
    sp.gateway.cmd('ip route replace 10.3.0.0/23 via 10.0.5.1')
    sp.gateway.cmd('ip route replace 10.4.0.0/23 via 10.0.5.1')
    sp.gateway.cmd('ip route replace default via 10.0.5.1')


    hq.gateway.cmd('ip route replace 10.2.0.0/23 via 10.0.5.2')
    hq.gateway.cmd('ip route replace 192.168.105.0/24 via 10.0.5.2')



    run_validation(net)
    t2.start_dhcp_clients()

    CLI(net)

    wh.stop_services()
    t2.stop_services()
    sp.stop_services()

    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    run()
