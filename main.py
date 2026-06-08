import sys

from mininet.net import Mininet
from mininet.node import OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel, info

from sites.hq import HQ
from sites.tienda1 import Tienda1
from sites.tienda2 import Tienda2
from sites.warehouse import Warehouse
from router import Router
from firewall import Firewall
from dhcp import DHCP
from tests import TestSuite

YELLOW = '\033[93m'
RESET  = '\033[0m'


class Topology:
    # sedes con interfaz Site estandar (build recibe router_cls)
    sites = [HQ(), Tienda1(), Tienda2()]

    # Warehouse tiene su propia interfaz: build(net) + configure() separado
    warehouse = Warehouse()

    # WAN: (router_a, alias_a, ip_a, router_b, alias_b, ip_b, bw_mbps, delay)
    # el nodo del warehouse se llama 'wh_r' (prefix='wh' + '_r')
    wan_links = [
        ('r_hq', 'rhq', '10.0.1.1', 'r_t1', 'rt1', '10.0.1.2', 20, '10ms'),  # HQ <-> Tienda1
        ('r_hq', 'rhq', '10.0.2.1', 'r_t2', 'rt2', '10.0.2.2', 20, '10ms'),  # HQ <-> Tienda2
        ('r_hq', 'rhq', '10.0.3.1', 'wh_r', 'whr', '10.0.3.2', 50, '8ms'),   # HQ <-> Warehouse
        ('r_t1', 'rt1', '10.0.4.1', 'wh_r', 'whr', '10.0.4.2', 15, '12ms'),  # Tienda1 <-> Warehouse
        ('r_t2', 'rt2', '10.0.5.1', 'wh_r', 'whr', '10.0.5.2', 15, '12ms'),  # Tienda2 <-> Warehouse
    ]

    # solo rutas remotas; las subredes directamente conectadas se aprenden solas
    # el Warehouse (wh_r) tambien recibe rutas estaticas aqui
    static_routes = {
        'r_hq': [
            'ip route add 10.2.0.0/23 via 10.0.1.2',   # -> Tienda1
            'ip route add 10.3.0.0/23 via 10.0.2.2',   # -> Tienda2
            'ip route add 10.4.0.0/23 via 10.0.3.2',   # -> Warehouse
        ],
        'r_t1': [
            'ip route add default via 10.0.1.1',
            'ip route add 10.4.0.0/23 via 10.0.4.2',   # Warehouse por enlace directo
        ],
        'r_t2': [
            'ip route add default via 10.0.2.1',
            'ip route add 10.4.0.0/23 via 10.0.5.2',
        ],
        # wh_r enruta hacia su LAN via el core switch (10.4.1.253, configurado por warehouse.configure())
        # y hacia las otras sedes via sus enlaces WAN
        'wh_r': [
            'ip route replace default via 10.0.3.1',        # salida por defecto via HQ
            'ip route replace 10.2.0.0/23 via 10.0.4.1',   # Tienda1 por enlace directo
            'ip route replace 10.3.0.0/23 via 10.0.5.1',   # Tienda2 por enlace directo
        ],
    }

    def __init__(self):
        self.net     = None
        self.routers = {}

    def _router_interfaces(self):
        # devuelve (router, interfaz, ip/cidr) de todas las interfaces de routers
        # las IPs se asignan despues de net.start() porque TCLink crea las interfaces en ese momento
        items = []
        for site in self.sites:
            for (hname, halias, vid, gw, hip, pfx, floor) in site.vlans:
                items.append((site.router, '%s-v%d' % (site.ralias, vid), '%s/%d' % (gw, pfx)))
        for (ra, aa, ipa, rb, ab, ipb, bw, delay) in self.wan_links:
            items.append((ra, '%s-%s' % (aa, ab), '%s/30' % ipa))
            items.append((rb, '%s-%s' % (ab, aa), '%s/30' % ipb))
        return items

    def _purge_orphaned_interfaces(self):
        from mininet.util import quietRun
        import re
        out = quietRun('ip link show')
        existing = set(re.findall(r'^\d+: ([^:@\s]+)', out, re.MULTILINE))
        # Prefijos que usa esta topologia; sistemas ajenos no deberían tenerlos
        prefixes = ('shq', 'st1', 'st2', 'swh', 'hhq', 'ht1', 'ht2', 'hwh',
                    'dhcp', 'rhq-', 'rt1-', 'rt2-', 'rwh-', 'whr-')
        for name in existing:
            if any(name.startswith(p) for p in prefixes):
                quietRun('ip link del ' + name)

    def build(self):
        self._purge_orphaned_interfaces()
        self.net = Mininet(controller=None, switch=OVSSwitch, link=TCLink)

        # sedes estandar: cada una construye su topologia y devuelve su router
        info('*** Creando topología por sede\n')
        for site in self.sites:
            r = site.build(self.net, Router)
            self.routers[site.router] = r

        # Warehouse tiene su propia interfaz de construccion
        self.warehouse.build(self.net)
        self.routers['wh_r'] = self.warehouse.wan_router

        # enlaces WAN con limite de ancho de banda y latencia simulada
        info('*** Creando enlaces WAN\n')
        for (ra, aa, ipa, rb, ab, ipb, bw, delay) in self.wan_links:
            self.net.addLink(self.net.get(ra), self.net.get(rb), cls=TCLink, bw=bw, delay=delay,
                             intfName1='%s-%s' % (aa, ab),
                             intfName2='%s-%s' % (ab, aa))

        info('*** Iniciando la red\n')
        self.net.start()

        # IPs asignadas explicitamente tras start(); TCLink crea las interfaces en ese momento
        info('*** Asignando IPs de routers\n')
        for rname, intf, cidr in self._router_interfaces():
            r = self.routers[rname]
            r.cmd('ip addr flush dev %s' % intf)
            r.cmd('ip addr add %s dev %s' % (cidr, intf))
            r.cmd('ip link set %s up' % intf)

        # Warehouse configura sus VLANs en OVS y el enlace interno core <-> wan_router
        info('*** Configurando Warehouse (OVS VLAN + gateways L3)\n')
        self.warehouse.configure()
        # el core switch del Warehouse hace L3; desactivar rp_filter en sus interfaces
        self.warehouse.core.cmd("for f in /proc/sys/net/ipv4/conf/*/rp_filter; do echo 0 > $f; done")

        # el valor efectivo de rp_filter es max(conf.all, conf.<intf>), hay que zerear cada interfaz
        info('*** Desactivando rp_filter por interfaz\n')
        for r in self.routers.values():
            r.cmd("for f in /proc/sys/net/ipv4/conf/*/rp_filter; do echo 0 > $f; done")

        info('*** Configurando rutas estaticas\n')
        for rname, cmds in self.static_routes.items():
            for c in cmds:
                out = self.routers[rname].cmd(c).strip()
                if out:  # cualquier salida indica error al aplicar la ruta
                    print('  %s[WARN]%s %s: "%s" -> %s' % (YELLOW, RESET, rname, c, out))

        # DHCP solo para sedes estandar; Warehouse tiene L3 en el core OVS con IPs estaticas
        info('*** Iniciando DHCP\n')
        DHCP().start(self.routers, self.sites)

        info('*** Aplicando firewall\n')
        Firewall().apply(self.routers)

    def run(self):
        self.build()

        suite = TestSuite()

        if '--diag' in sys.argv:
            suite.dump_diagnostics(self.routers)

        if '--skip-tests' not in sys.argv:
            suite.run(self.net)
        else:
            suite.print_suggested_commands()

        CLI(self.net)
        self.net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    Topology().run()
