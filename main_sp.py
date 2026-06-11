from mininet.net import Mininet
from mininet.node import OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel

from sites.tiendaSanPedro import TiendaSanPedro

BOLD  = '\033[1m'
CYAN  = '\033[96m'
GREEN = '\033[92m'
RED   = '\033[91m'
RESET = '\033[0m'

# (host, vlan, label)
SP_HOSTS = [
    ('sp_hwifi',   130, 'WiFi'),
    ('sp_hchk',    140, 'Checkout'),
    ('sp_hadmin',   40, 'Admin'),
    ('sp_hsec',     30, 'Security'),
    ('sp_hcam',    100, 'Camaras'),
    ('sp_hprint',  110, 'Impresoras'),
    ('sp_hphone',  120, 'Telefonos'),
]


def dhcp_all(net):
    """
    Pide lease DHCP a todos los hosts via proceso DORA.
    Necesario antes de pingall porque los hosts tienen ip=None —
    sin DHCP Mininet no conoce sus IPs y pingall falla.
    """
    print(f'\n{BOLD}{CYAN}=== DHCP: solicitando IPs (DORA) ==={RESET}')

    for host_name, vlan, label in SP_HOSTS:
        h = net.get(host_name)
        pid_path   = f'tmp/dhclient-{host_name}.pid'
        lease_path = f'tmp/dhclient-{host_name}.leases'

        h.cmd(f'touch {lease_path}')
        h.cmd(f'dhclient -4 -r -pf {pid_path} -lf {lease_path} {host_name}-eth0 2>/dev/null || true')
        h.cmd(f'ip addr flush dev {host_name}-eth0')
        out = h.cmd(f'timeout 20 dhclient -4 -1 -v -pf {pid_path} -lf {lease_path} {host_name}-eth0 2>&1')

        ip_line = h.cmd(f'ip -4 addr show dev {host_name}-eth0 | grep inet').strip().replace('\r', '')

        if 'bound to' in out and ip_line:
            ip = ip_line.split()[1]
            print(f'{GREEN}[OK]{RESET}   {host_name:12} VLAN {vlan:3} {label:12} → {ip}')
        else:
            print(f'{RED}[FAIL]{RESET} {host_name:12} VLAN {vlan:3} {label:12} → sin lease')


def run():
    net = Mininet(
        controller=None,
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True,
        autoStaticArp=False
    )

    sp = TiendaSanPedro()
    sp.build(net)

    net.start()
    sp.configure()

    # 1. DORA: todos los hosts piden IP por DHCP
    #    Sin este paso, h.IP() devuelve None y pingall falla
    dhcp_all(net)

    # 2. pingall — ahora h.IP() conoce la IP asignada por DHCP
    print(f'\n{BOLD}{CYAN}=== pingall inter-VLAN ==={RESET}')
    net.pingAll()

    # 3. CLI para pruebas manuales
    CLI(net)

    sp.stop_services()
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    run()
