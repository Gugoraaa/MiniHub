#!/usr/bin/env python3

import sys
from pathlib import Path

from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.node import OVSSwitch

MINIHUB_DIR = Path(__file__).resolve().parent / 'MiniHub'
sys.path.insert(0, str(MINIHUB_DIR))

from sites.hq import HQSite


def build_master():
    net = Mininet(
        controller=None,
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True,
        autoStaticArp=False,
    )

    hq = HQSite()
    hq.build(net)

    net.start()
    hq.configure()

    print('\n=== HQ topology loaded ===')
    print('Pruebas sugeridas dentro de Mininet:')
    print('  hq_it ping -c 3 10.1.0.1')
    print('  hq_it ping -c 3 hq_sales')
    print('  hq_it ping -c 3 hq_finance')
    print('  hq_finance ping -c 3 hq_camera')
    print('  hq_sales ping -c 3 hq_phone')
    print('  s5 ping -c 3 10.1.2.2')
    print('  hq_it ping -c 3 10.1.2.2')
    print('==========================\n')

    CLI(net)
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    build_master()
