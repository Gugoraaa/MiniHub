from mininet.net import Mininet
from mininet.node import OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel

from sites.warehouse import Warehouse
from sites.hq import HQSite


def run():
    net = Mininet(
        controller=None,
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True,
        autoStaticArp=False
    )

    hq = HQSite()
    wh = Warehouse(net)

    hq.build(net)

    # Enlace WAN Warehouse <-> HQ
    net.addLink(
        wh.r_wh,
        hq.gateway,
        intfName1='r_wh-eth1',
        intfName2='hqr-eth1',
        
    )

    net.start()

    hq.configure()
    wh.configure()

    # =========================
    # WAN HQ <-> Warehouse
    # Red: 10.0.3.0/30
    # hqr  = 10.0.3.1/30
    # r_wh = 10.0.3.2/30
    # =========================

    hq.gateway.cmd('ip addr flush dev hqr-eth1')
    hq.gateway.setIP('10.0.3.1/30', intf='hqr-eth1')
    hq.gateway.cmd('ip link set hqr-eth1 up')

    wh.r_wh.cmd('ip addr flush dev r_wh-eth1')
    wh.r_wh.setIP('10.0.3.2/30', intf='r_wh-eth1')
    wh.r_wh.cmd('ip link set r_wh-eth1 up')

    # Rutas en router Warehouse
    wh.r_wh.cmd('ip route replace 10.1.0.0/23 via 10.0.3.1')
    wh.r_wh.cmd('ip route replace default via 10.0.3.1')

    # Rutas en router HQ
    hq.gateway.cmd('ip route replace 10.4.0.0/23 via 10.0.3.2')
    hq.gateway.cmd('ip route replace 192.168.104.0/24 via 10.0.3.2')

    CLI(net)

    wh.stop_services()

    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    run()