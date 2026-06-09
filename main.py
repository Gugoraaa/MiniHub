from mininet.net import Mininet
from mininet.node import OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel

from sites.warehouse import Warehouse


def run():
    # Crear red vacía
    net = Mininet(
        controller=None,
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True,
        autoStaticArp=False
    )

    # Crear topología del almacén
    wh = Warehouse(net)

    # Iniciar red
    net.start()

    # Configurar VLANs, trunks, SVIs, rutas, etc.
    wh.configure()

    print('\n=== Warehouse topology loaded ===')
    print('Pruebas sugeridas dentro de Mininet:')
    print('  ic1 ping -c 3 10.4.0.1')
    print('  ic1 ping -c 3 office1')
    print('  camF1 ping -c 3 camF2')
    print('  ic1 ping -c 3 10.4.1.254')
    print('  mls ping -c 3 10.4.1.254')
    print('=================================\n')

    # Abrir consola Mininet
    CLI(net)

    # Detener red al salir
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    run()