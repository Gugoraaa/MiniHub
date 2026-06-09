#!/usr/bin/env python3

from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.node import OVSSwitch

from sites.hqpoststart import HQPostStart


def run():
    net = Mininet(
        controller=None,
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True,
        autoStaticArp=False,
    )

    try:
        hq = HQPostStart()
        hq.build(net)

        net.start()

        hq.addlinks(net)
        hq.configure()

        print('\n=== HQ post-start link experiment loaded ===')
        print('Pruebas sugeridas dentro de Mininet:')
        print('  nodes')
        print('  links')
        print('  hit ip addr')
        print('  s5 ip addr')
        print('  hit ping -c 3 10.1.0.1')
        print('  hit ping -c 3 hsales')
        print('  hit ping -c 3 hfin')
        print('  hfin ping -c 3 hcam')
        print('  s5 ping -c 3 10.1.2.2')
        print('  hqr ping -c 3 10.1.2.1')
        print('  hit ping -c 3 10.1.2.2')
        print('===========================================\n')

        CLI(net)
    finally:
        net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    run()
