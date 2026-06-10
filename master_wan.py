#!/usr/bin/env python3

import os
import subprocess

from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.node import OVSSwitch

from sites.hq import HQSite


BASEDIR = os.path.dirname(os.path.abspath(__file__))


def runclean():
    subprocess.run(['bash', os.path.join(BASEDIR, 'clean.sh')], check=False)


def buildmaster():
    os.chdir(BASEDIR)
    runclean()

    net = Mininet(
        controller=None,
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True,
        autoStaticArp=False,
    )

    try:
        hq = HQSite()
        hq.build(net)

        net.start()
        hq.configure()

        print('\n=== HQ topology loaded ===')
        print('Pruebas sugeridas dentro de Mininet:')
        print('  hit ping -c 3 10.1.0.1')
        print('  hit ping -c 3 hsales')
        print('  hit ping -c 3 hfin')
        print('  hfin ping -c 3 hcam')
        print('  hsales ping -c 3 hphone')
        print('  s5 ping -c 3 10.1.2.2')
        print('  hqr ping -c 3 10.1.2.1')
        print('  hit ping -c 3 10.1.2.2')
        print('  hit ping -c 3 10.1.0.10')
        print('  hit nslookup dns.hq.local 10.1.0.10')
        print('  hit nslookup router.hq.local 10.1.0.10')
        print('  hit nslookup dns.hq.local')
        print('==========================\n')

        CLI(net)
    finally:
        net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    buildmaster()
