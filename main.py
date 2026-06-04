import ipaddress
import re
import sys
import time

from mininet.net import Mininet
from mininet.node import Node, OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel, info

# Colores ANSI para la salida de tests
GREEN  = '\033[92m'
RED    = '\033[91m'
YELLOW = '\033[93m'
BOLD   = '\033[1m'
RESET  = '\033[0m'


# ---------------------------------------------------------------------------
# Clase Router (patron de clase, s7exe.pdf) + endurecimiento para plano compartido
# ---------------------------------------------------------------------------
class LinuxRouter(Node):
    """Host Linux que enruta entre sus interfaces."""

    def config(self, **params):
        super(LinuxRouter, self).config(**params)
        # Reenvio IPv4
        self.cmd('sysctl -w net.ipv4.ip_forward=1')
        # Desactivar Reverse Path Filtering (rutas asimetricas WAN)
        self.cmd('sysctl -w net.ipv4.conf.all.rp_filter=0')
        self.cmd('sysctl -w net.ipv4.conf.default.rp_filter=0')
        # Evitar ARP flux: cada interfaz responde ARP solo por su propia IP
        self.cmd('sysctl -w net.ipv4.conf.all.arp_ignore=1')
        self.cmd('sysctl -w net.ipv4.conf.all.arp_announce=2')

    def terminate(self):
        self.cmd('sysctl -w net.ipv4.ip_forward=0')
        super(LinuxRouter, self).terminate()


# ---------------------------------------------------------------------------
# Generador de nombres de interfaz cortos (Linux limita IFNAMSIZ a 15 chars).
# Los nombres de NODO si pueden ser largos/descriptivos; las INTERFACES no.
# ---------------------------------------------------------------------------
_if_count = {}
_sw_dpid = 0


def _ifn(alias):
    """Devuelve un nombre de interfaz unico y corto para el alias dado."""
    n = _if_count.get(alias, 0)
    _if_count[alias] = n + 1
    return '%s-%d' % (alias, n)


def _dpid():
    """Datapath ID unico para cada switch (OVS no puede derivarlo de nombres descriptivos)."""
    global _sw_dpid
    _sw_dpid += 1
    return '%016x' % _sw_dpid


def _dhcp_range(gw_str, host_ip_str, pfx):
    """Calcula rango DHCP (start, end, mask) sin solapar gateway ni host representativo.
    Usa la mitad superior del pool disponible. Retorna None si no hay espacio (/30)."""
    net = ipaddress.ip_network('%s/%d' % (gw_str, pfx), strict=False)
    excluded = {ipaddress.ip_address(gw_str), ipaddress.ip_address(host_ip_str)}
    pool = [h for h in net.hosts() if h not in excluded]
    if len(pool) < 2:
        return None  # /30: solo 2 IPs utiles, no queda espacio para pool
    mid = len(pool) // 2
    return str(pool[mid]), str(pool[-1]), str(net.netmask)


def router_interfaces():
    """Lista (router, nombre_interfaz, ip/cidr) de TODAS las interfaces de routers.
    Incluye la interfaz-gateway por VLAN (LAN) y las interfaces WAN /30. Las IPs se
    aplican explicitamente tras net.start() para ser deterministas con TCLink."""
    items = []
    for s in SITES.values():
        for (hname, halias, vid, gw, hip, pfx, floor) in s['vlans']:
            items.append((s['router'], '%s-v%d' % (s['ralias'], vid), '%s/%d' % (gw, pfx)))
    for (ra, aa, ipa, rb, ab, ipb, bw, delay) in WAN_LINKS:
        items.append((ra, '%s-%s' % (aa, ab), '%s/30' % ipa))
        items.append((rb, '%s-%s' % (ab, aa), '%s/30' % ipb))
    return items


# ---------------------------------------------------------------------------
# DISENO IP / VLSM OFICIAL  (no inventar rangos)
# Cada entrada de VLAN:
#   nombre_host, alias_if, vlan_id, gateway, host_ip, prefijo, piso(1..N)
# El gateway y el host comparten prefijo. El router crea una interfaz por VLAN
# llamada "<ralias>-v<vlan_id>" con IP "<gateway>/<prefijo>".
# ---------------------------------------------------------------------------
SITES = {
    'hq': {
        'router': 'r_hq', 'ralias': 'rhq',
        'core': 's_hq_core', 'calias': 'shqc',
        'floors': {1: ('s_hq_floor1', 'shqf1'),
                   2: ('s_hq_floor2', 'shqf2'),
                   3: ('s_hq_floor3', 'shqf3'),
                   4: ('s_hq_floor4', 'shqf4')},
        'block': '10.1.0.0/23',
        'vlans': [
            # host,                 alias,   vid, gateway,      host_ip,      pfx, floor
            ('h_hq_it',             'hhqit', 10,  '10.1.0.1',   '10.1.0.10',  27, 4),
            ('h_hq_sales',          'hhqsa', 20,  '10.1.0.33',  '10.1.0.40',  27, 2),
            ('h_hq_security_ops',   'hhqso', 30,  '10.1.0.65',  '10.1.0.70',  27, 1),
            ('h_hq_management',     'hhqmg', 40,  '10.1.0.97',  '10.1.0.100', 27, 3),
            ('h_hq_hr',             'hhqhr', 50,  '10.1.0.129', '10.1.0.130', 27, 3),
            ('h_hq_finance',        'hhqfi', 60,  '10.1.0.161', '10.1.0.170', 27, 4),
            ('h_hq_inventory',      'hhqiv', 70,  '10.1.0.193', '10.1.0.200', 27, 1),
            ('h_hq_customer_service','hhqcs', 80, '10.1.1.1',   '10.1.1.10',  27, 2),
            ('h_hq_procurement',    'hhqpc', 90,  '10.1.1.33',  '10.1.1.40',  27, 4),
            ('h_hq_camera',         'hhqcm', 100, '10.1.1.65',  '10.1.1.70',  27, 1),
            ('h_hq_printer',        'hhqpr', 110, '10.1.1.97',  '10.1.1.100', 27, 4),
            ('h_hq_phone',          'hhqpn', 120, '10.1.1.129', '10.1.1.130', 27, 2),
        ],
    },
    't1': {
        'router': 'r_t1', 'ralias': 'rt1',
        'core': 's_t1_core', 'calias': 'st1c',
        'floors': {1: ('s_t1_floor1', 'st1f1'),
                   2: ('s_t1_floor2', 'st1f2')},
        'block': '10.2.0.0/23',
        'vlans': [
            ('h_t1_wifi_guest', 'ht1wg', 130, '10.2.0.1',  '10.2.0.10', 24, 2),
            ('h_t1_checkout',   'ht1ck', 140, '10.2.1.1',  '10.2.1.10', 27, 1),
            ('h_t1_admin',      'ht1ad', 40,  '10.2.1.33', '10.2.1.34', 28, 2),
            ('h_t1_security',   'ht1se', 30,  '10.2.1.49', '10.2.1.50', 28, 1),
            ('h_t1_camera',     'ht1cm', 100, '10.2.1.65', '10.2.1.66', 28, 1),
            ('h_t1_printer',    'ht1pr', 110, '10.2.1.81', '10.2.1.82', 29, 2),
            ('h_t1_phone',      'ht1pn', 120, '10.2.1.89', '10.2.1.90', 30, 2),
        ],
    },
    't2': {
        'router': 'r_t2', 'ralias': 'rt2',
        'core': 's_t2_core', 'calias': 'st2c',
        'floors': {1: ('s_t2_floor1', 'st2f1'),
                   2: ('s_t2_floor2', 'st2f2')},
        'block': '10.3.0.0/23',
        'vlans': [
            ('h_t2_wifi_guest', 'ht2wg', 130, '10.3.0.1',  '10.3.0.10', 24, 2),
            ('h_t2_checkout',   'ht2ck', 140, '10.3.1.1',  '10.3.1.10', 27, 1),
            ('h_t2_admin',      'ht2ad', 40,  '10.3.1.33', '10.3.1.34', 28, 2),
            ('h_t2_security',   'ht2se', 30,  '10.3.1.49', '10.3.1.50', 28, 1),
            ('h_t2_camera',     'ht2cm', 100, '10.3.1.65', '10.3.1.66', 28, 1),
            ('h_t2_printer',    'ht2pr', 110, '10.3.1.81', '10.3.1.82', 29, 2),
            ('h_t2_phone',      'ht2pn', 120, '10.3.1.89', '10.3.1.90', 30, 2),
        ],
    },
    'wh': {
        'router': 'r_wh', 'ralias': 'rwh',
        'core': 's_wh_core', 'calias': 'swhc',
        'floors': {1: ('s_wh_floor1', 'swhf1'),
                   2: ('s_wh_floor2', 'swhf2')},
        'block': '10.4.0.0/23',
        'vlans': [
            ('h_wh_inventory', 'hwhiv', 70,  '10.4.0.1',   '10.4.0.10',  27, 1),
            ('h_wh_admin',     'hwhad', 40,  '10.4.0.33',  '10.4.0.34',  27, 2),
            ('h_wh_receiving', 'hwhrc', 150, '10.4.0.65',  '10.4.0.70',  27, 1),
            ('h_wh_shipping',  'hwhsh', 160, '10.4.0.97',  '10.4.0.100', 28, 1),
            ('h_wh_security',  'hwhse', 30,  '10.4.0.113', '10.4.0.114', 28, 1),
            ('h_wh_camera',    'hwhcm', 100, '10.4.0.129', '10.4.0.130', 28, 1),
            ('h_wh_printer',   'hwhpr', 110, '10.4.0.145', '10.4.0.146', 29, 2),
            ('h_wh_phone',     'hwhpn', 120, '10.4.0.153', '10.4.0.154', 30, 2),
        ],
    },
}

# ---------------------------------------------------------------------------
# ENLACES WAN /30 con TCLink (ancho de banda + latencia).  Brief seccion 7 y 8.
#   (router_a, ralias_a, ip_a, router_b, ralias_b, ip_b, bw_mbps, delay)
# ---------------------------------------------------------------------------
WAN_LINKS = [
    ('r_hq', 'rhq', '10.0.1.1', 'r_t1', 'rt1', '10.0.1.2', 20, '10ms'),  # HQ <-> Tienda1
    ('r_hq', 'rhq', '10.0.2.1', 'r_t2', 'rt2', '10.0.2.2', 20, '10ms'),  # HQ <-> Tienda2
    ('r_hq', 'rhq', '10.0.3.1', 'r_wh', 'rwh', '10.0.3.2', 50, '8ms'),   # HQ <-> Warehouse
    ('r_t1', 'rt1', '10.0.4.1', 'r_wh', 'rwh', '10.0.4.2', 15, '12ms'),  # Tienda1 <-> Warehouse
    ('r_t2', 'rt2', '10.0.5.1', 'r_wh', 'rwh', '10.0.5.2', 15, '12ms'),  # Tienda2 <-> Warehouse
]

# ---------------------------------------------------------------------------
# RUTAS ESTATICAS (brief seccion 7). Las subredes directamente conectadas se
# aprenden solas; aqui solo las remotas. Las /30 WAN son adyacentes a cada via.
# ---------------------------------------------------------------------------
STATIC_ROUTES = {
    'r_hq': [
        'ip route add 10.2.0.0/23 via 10.0.1.2',   # -> Tienda 1
        'ip route add 10.3.0.0/23 via 10.0.2.2',   # -> Tienda 2
        'ip route add 10.4.0.0/23 via 10.0.3.2',   # -> Warehouse
    ],
    'r_t1': [
        'ip route add default via 10.0.1.1',        # todo lo demas via HQ
        'ip route add 10.4.0.0/23 via 10.0.4.2',    # Warehouse por enlace directo
    ],
    'r_t2': [
        'ip route add default via 10.0.2.1',
        'ip route add 10.4.0.0/23 via 10.0.5.2',
    ],
    'r_wh': [
        'ip route add default via 10.0.3.1',
        'ip route add 10.2.0.0/23 via 10.0.4.1',    # Tienda 1 por enlace directo
        'ip route add 10.3.0.0/23 via 10.0.5.1',    # Tienda 2 por enlace directo
    ],
}


# ---------------------------------------------------------------------------
# Construccion de la topologia
# ---------------------------------------------------------------------------
def build():
    net = Mininet(controller=None, switch=OVSSwitch, link=TCLink)

    routers = {}     # nombre_router -> nodo
    info('*** Creando routers, switches y hosts por sede\n')

    for skey, s in SITES.items():
        # Router de la sede
        r = net.addHost(s['router'], cls=LinuxRouter)
        routers[s['router']] = r

        # Switch core + switches de piso (modo standalone: switch L2 normal)
        # dpid explicito: OVS no puede derivar el datapath ID de nombres descriptivos.
        core = net.addSwitch(s['core'], failMode='standalone', dpid=_dpid())
        floor_sw = {}
        for fnum, (fname, falias) in s['floors'].items():
            floor_sw[fnum] = (net.addSwitch(fname, failMode='standalone', dpid=_dpid()), falias)
            # piso -> core
            net.addLink(floor_sw[fnum][0], core,
                        intfName1=_ifn(falias), intfName2=_ifn(s['calias']))

        # Hosts representativos + enlace router(core) por cada VLAN
        for (hname, halias, vid, gw, hip, pfx, floor) in s['vlans']:
            host = net.addHost(hname, ip='%s/%d' % (hip, pfx),
                               defaultRoute='via %s' % gw)
            # host -> switch de piso
            fsw, falias = floor_sw[floor]
            net.addLink(host, fsw, intfName1=_ifn(halias), intfName2=_ifn(falias))
            # router -> core (la IP gateway de la VLAN se asigna tras net.start(),
            # patron de clase s7exe.pdf; mas fiable que params1 con TCLink).
            net.addLink(r, core,
                        intfName1='%s-v%d' % (s['ralias'], vid),
                        intfName2=_ifn(s['calias']))

    # Nodo representativo del servicio DHCP (IPs estaticas por estabilidad).
    # Se documenta como abstraccion del servidor DHCP centralizado de HQ.
    dhcp = net.addHost('dhcp_hq', ip='10.1.0.11/27', defaultRoute='via 10.1.0.1')
    net.addLink(dhcp, net.get('s_hq_floor4'),
                intfName1=_ifn('dhcphq'), intfName2=_ifn('shqf4'))

    # Enlaces WAN /30 con limites de ancho de banda y latencia.
    # Las IPs se asignan tras net.start() (ver router_interfaces()).
    info('*** Creando enlaces WAN (TCLink con bw/delay)\n')
    for (ra, aa, ipa, rb, ab, ipb, bw, delay) in WAN_LINKS:
        net.addLink(net.get(ra), net.get(rb), cls=TCLink, bw=bw, delay=delay,
                    intfName1='%s-%s' % (aa, ab),
                    intfName2='%s-%s' % (ab, aa))

    info('*** Iniciando la red\n')
    net.start()

    # IPs de router (gateways de VLAN + WAN) asignadas explicitamente tras start.
    info('*** Asignando IPs de routers (LAN gateways + WAN)\n')
    for rname, intf, cidr in router_interfaces():
        r = routers[rname]
        r.cmd('ip addr flush dev %s' % intf)
        r.cmd('ip addr add %s dev %s' % (cidr, intf))
        r.cmd('ip link set %s up' % intf)

    # rp_filter efectivo = max(conf.all, conf.<intf>); como las interfaces ya
    # existen al arrancar, forzamos 0 en CADA interfaz de cada router para que el
    # Reverse Path Filtering no descarte trafico en el plano L2 compartido.
    info('*** Desactivando rp_filter por interfaz en los routers\n')
    for r in routers.values():
        r.cmd("for f in /proc/sys/net/ipv4/conf/*/rp_filter; do echo 0 > $f; done")

    # Rutas estaticas (se captura cualquier error de aplicacion)
    info('*** Configurando rutas estaticas\n')
    for rname, cmds in STATIC_ROUTES.items():
        for c in cmds:
            out = routers[rname].cmd(c).strip()
            if out:
                print('  %s[WARN]%s %s: "%s" -> %s' % (YELLOW, RESET, rname, c, out))

    # DHCP: dnsmasq en cada router sirviendo su pool de VLANs
    info('*** Iniciando servidores DHCP (dnsmasq por router)\n')
    start_dhcp(routers)

    # Firewall
    info('*** Aplicando reglas de firewall (iptables)\n')
    apply_firewall(routers)

    if '--diag' in sys.argv:
        dump_diagnostics(routers)

    if '--skip-tests' not in sys.argv:
        run_tests(net)
    else:
        print_suggested_commands()

    CLI(net)
    net.stop()


# ---------------------------------------------------------------------------
# DHCP
# ---------------------------------------------------------------------------
def start_dhcp(routers):
    """Inicia dnsmasq en cada router como servidor DHCP para todas sus VLANs.

    Los hosts representativos conservan sus IPs estaticas (que estan fuera del
    pool DHCP). Cualquier host adicional que se conecte a la red recibira una IP
    por DHCP desde el router de su sede.

    Para demostrar que funciona desde la CLI de Mininet:
        h_hq_sales ip addr flush dev h_hq_sales-eth0
        h_hq_sales dhclient -v h_hq_sales-eth0
        h_hq_sales ip addr
    """
    probe = list(routers.values())[0].cmd('which dnsmasq 2>/dev/null').strip()
    if not probe:
        print('%s[WARN] dnsmasq no encontrado — DHCP no disponible.%s' % (YELLOW, RESET))
        print('       Instala con: sudo apt-get install -y dnsmasq')
        return

    for skey, s in SITES.items():
        r = routers[s['router']]
        # Limpiar instancias anteriores en este namespace
        r.cmd('pkill -f "dnsmasq.*%s" 2>/dev/null; true' % skey)

        args = [
            'dnsmasq',
            '--no-resolv',
            '--no-hosts',
            '--bind-interfaces',
            '--except-interface=lo',
            '--pid-file=/tmp/dnsmasq-%s.pid' % skey,
            '--log-facility=/tmp/dnsmasq-%s.log' % skey,
        ]

        served = 0
        for (hname, halias, vid, gw, hip, pfx, floor) in s['vlans']:
            result = _dhcp_range(gw, hip, pfx)
            if result is None:
                continue  # /30 sin espacio para pool
            start, end, mask = result
            tag = 'vid%d' % vid
            intf = '%s-v%d' % (s['ralias'], vid)
            args += [
                '--interface=%s' % intf,
                '--dhcp-range=tag:%s,%s,%s,%s,12h' % (tag, start, end, mask),
                '--dhcp-option=tag:%s,option:router,%s' % (tag, gw),
            ]
            served += 1

        if served == 0:
            continue

        out = r.cmd(' '.join(args) + ' 2>&1').strip()
        if out:
            print('%s[WARN]%s dnsmasq %s: %s' % (YELLOW, RESET, skey, out))
        else:
            info('*** DHCP activo en %s (%d VLANs)\n' % (s['router'], served))


# ---------------------------------------------------------------------------
# FIREWALL (brief seccion 10).  Politica por defecto ACCEPT + reglas dirigidas.
# IMPORTANTE: las reglas ACCEPT deben ir ANTES que los DROP generales.
# ---------------------------------------------------------------------------
# Subredes de servicios sensibles (coinciden con el VLSM oficial)
HQ_PRINTERS = '10.1.1.96/27'
HQ_CAMERAS = '10.1.1.64/27'
HQ_FINANCE = '10.1.0.160/27'
HQ_IT = '10.1.0.0/27'
HQ_MGMT = '10.1.0.96/27'
HQ_SECOPS = '10.1.0.64/27'
HQ_SALES = '10.1.0.32/27'
HQ_HR = '10.1.0.128/27'
HQ_CUSTSVC = '10.1.1.0/27'


def apply_firewall(routers):
    rhq = routers['r_hq']

    # Verificar que iptables exista y funcione en el namespace del router.
    probe = rhq.cmd('iptables -L FORWARD -n 2>&1')
    if ('Chain FORWARD' not in probe):
        print('%s%s[ERROR] iptables no funciona en este sistema:%s %s' % (
            BOLD, RED, RESET, probe.strip().splitlines()[0] if probe.strip() else '(sin salida)'))
        print('%s        Instala iptables:  sudo apt-get install -y iptables%s' % (YELLOW, RESET))
        print('%s        Sin iptables los tests de seguridad NO bloquearan trafico.%s' % (YELLOW, RESET))

    def hq(rule):
        rhq.cmd('iptables ' + rule)

    # --- r_hq: politica por defecto -------------------------------------
    hq('-P FORWARD ACCEPT')

    # --- Politica 2: camaras (PERMITIR SecOps primero, luego BLOQUEAR resto)
    hq('-A FORWARD -s %s -d %s -j ACCEPT' % (HQ_SECOPS, HQ_CAMERAS))   # SecOps -> camaras OK

    # --- Politica 4: Finance (PERMITIR IT/Management primero)
    hq('-A FORWARD -s %s -d %s -j ACCEPT' % (HQ_IT, HQ_FINANCE))
    hq('-A FORWARD -s %s -d %s -j ACCEPT' % (HQ_MGMT, HQ_FINANCE))

    # --- Politica 1: impresoras (usuarios comunes NO acceden a impresoras HQ)
    hq('-A FORWARD -s %s -d %s -j DROP' % (HQ_SALES, HQ_PRINTERS))     # Sales
    hq('-A FORWARD -s %s -d %s -j DROP' % (HQ_HR, HQ_PRINTERS))        # HR
    hq('-A FORWARD -s %s -d %s -j DROP' % (HQ_CUSTSVC, HQ_PRINTERS))   # Customer Service

    # --- Politica 2 (cont.): bloquear a TODOS los demas hacia camaras HQ
    hq('-A FORWARD -d %s -j DROP' % HQ_CAMERAS)

    # --- Politica 4 (cont.): bloquear a TODOS los demas hacia Finance HQ
    hq('-A FORWARD -d %s -j DROP' % HQ_FINANCE)

    # --- Politica 3: WiFi Invitados de tiendas NO accede a redes internas ---
    internal = ['10.1.0.0/23', '10.2.1.0/24', '10.3.1.0/24', '10.4.0.0/23']
    for site, router_name, guest_net, local_net in [
        ('t1', 'r_t1', '10.2.0.0/24', '10.2.1.0/24'),
        ('t2', 'r_t2', '10.3.0.0/24', '10.3.1.0/24'),
    ]:
        rt = routers[router_name]
        rt.cmd('iptables -P FORWARD ACCEPT')
        for dst in internal:
            rt.cmd('iptables -A FORWARD -s %s -d %s -j DROP' % (guest_net, dst))
        # Aislamiento local de impresoras/camaras de la tienda (usuarios comunes)
        store_printers = '10.2.1.80/29' if site == 't1' else '10.3.1.80/29'
        store_cameras = '10.2.1.64/28' if site == 't1' else '10.3.1.64/28'
        checkout = '10.2.1.0/27' if site == 't1' else '10.3.1.0/27'
        rt.cmd('iptables -A FORWARD -s %s -d %s -j DROP' % (checkout, store_printers))
        rt.cmd('iptables -A FORWARD -s %s -d %s -j DROP' % (checkout, store_cameras))

    # --- Warehouse: aislamiento local de impresoras/camaras -------------
    rwh = routers['r_wh']
    rwh.cmd('iptables -P FORWARD ACCEPT')
    rwh.cmd('iptables -A FORWARD -s 10.4.0.32/27 -d 10.4.0.144/29 -j DROP')  # admin -> impresoras
    rwh.cmd('iptables -A FORWARD -s 10.4.0.96/28 -d 10.4.0.128/28 -j DROP')  # shipping -> camaras


# ---------------------------------------------------------------------------
def dump_diagnostics(routers):
    """Imprime IPs y rutas de cada router + reglas FORWARD de r_hq (flag --diag)."""
    sep = '-' * 64
    for name in ['r_hq', 'r_t1', 'r_t2', 'r_wh']:
        r = routers[name]
        print('\n%s\n  DIAG %s\n%s' % (sep, name, sep))
        print('[ip -br -4 addr]')
        print(r.cmd('ip -br -4 addr').rstrip())
        print('[ip route]')
        print(r.cmd('ip route').rstrip())
    print('\n%s\n  DIAG r_hq iptables FORWARD\n%s' % (sep, sep))
    print(routers['r_hq'].cmd('iptables -S FORWARD').rstrip())
    print(sep + '\n')


# ---------------------------------------------------------------------------
def run_tests(net):
    """Ejecuta todos los tests automaticamente y muestra resultados con PASS/FAIL."""

    results = []

    def _ping(label, src_name, dst_name, expect_ok):
        src = net.get(src_name)
        dst = net.get(dst_name)
        out = src.cmd('ping -c 3 -W 2 %s' % dst.IP())
        m = re.search(r'(\d+)% packet loss', out)
        loss = int(m.group(1)) if m else 100
        ok = (loss == 0) if expect_ok else (loss == 100)
        results.append(ok)
        tag = 'FUNCIONA' if expect_ok else 'BLOQUEADO'
        status = GREEN + 'PASS' + RESET if ok else RED + 'FAIL' + RESET
        print('  [%s] %-48s  %d%% loss' % (
            status, '%s -> %s  [%s]' % (src_name, dst_name, tag), loss))
        return ok

    def _iperf(label, server_name, client_name, server_ip, limit_mbps):
        sv = net.get(server_name)
        cl = net.get(client_name)
        sv.cmd('pkill -f "iperf -s" 2>/dev/null; iperf -s &')
        time.sleep(1)
        out = cl.cmd('iperf -c %s -t 5' % server_ip)
        sv.cmd('pkill -f "iperf -s" 2>/dev/null')
        m = re.search(r'([\d.]+)\s+Mbits/sec', out)
        mbps = float(m.group(1)) if m else 0.0
        ok = 0 < mbps <= limit_mbps * 1.2
        results.append(ok)
        status = GREEN + 'PASS' + RESET if ok else RED + 'FAIL' + RESET
        print('  [%s] %-48s  %.1f Mbps  (limite %d Mbps)' % (status, label, mbps, limit_mbps))
        return ok

    sep = '=' * 64

    print('\n' + BOLD + sep + RESET)
    print(BOLD + '  A. CONNECTIVITY TESTS  (deben FUNCIONAR)' + RESET)
    print(sep)
    _ping('T1 checkout -> HQ sales',         'h_t1_checkout',          'h_hq_sales',      True)
    _ping('T2 checkout -> HQ sales',         'h_t2_checkout',          'h_hq_sales',      True)
    _ping('WH inventory -> HQ inventory',    'h_wh_inventory',         'h_hq_inventory',  True)
    _ping('HQ IT -> WH admin',               'h_hq_it',                'h_wh_admin',      True)
    _ping('T1 checkout -> WH inventory',     'h_t1_checkout',          'h_wh_inventory',  True)

    print('\n' + BOLD + sep + RESET)
    print(BOLD + '  B. SECURITY TESTS  (firewall iptables)' + RESET)
    print(sep)
    _ping('WiFi guest T1 -> HQ sales',       'h_t1_wifi_guest',        'h_hq_sales',      False)
    _ping('HQ sales -> HQ printer',          'h_hq_sales',             'h_hq_printer',    False)
    _ping('HQ cust.svc -> HQ finance',       'h_hq_customer_service',  'h_hq_finance',    False)
    _ping('HQ security_ops -> HQ camera',   'h_hq_security_ops',      'h_hq_camera',     True)
    _ping('HQ sales -> HQ camera',           'h_hq_sales',             'h_hq_camera',     False)

    print('\n' + BOLD + sep + RESET)
    print(BOLD + '  C. BANDWIDTH TESTS  (iperf / TCLink)' + RESET)
    print(sep)
    _iperf('HQ sales  <- T1 checkout    (WAN 20 Mbps)',
           'h_hq_sales',      'h_t1_checkout',   '10.1.0.40',  20)
    _iperf('HQ inventory <- WH inventory (WAN 50 Mbps)',
           'h_hq_inventory',  'h_wh_inventory',  '10.1.0.200', 50)
    _iperf('WH inventory <- T1 checkout  (directo 15 Mbps)',
           'h_wh_inventory',  'h_t1_checkout',   '10.4.0.10',  15)

    passed = sum(results)
    total  = len(results)
    color  = GREEN if passed == total else (YELLOW if passed >= total * 0.7 else RED)
    print('\n' + sep)
    print('  RESULTADO: %s%s%d / %d tests pasaron%s' % (
        BOLD, color, passed, total, RESET))
    print(sep + '\n')


# ---------------------------------------------------------------------------
def print_suggested_commands():
    print("\n" + "=" * 60)
    print("MiniHUB listo. Comandos sugeridos dentro de la CLI de Mininet:")
    print("=" * 60)
    print("=== Connectivity Tests (deben FUNCIONAR) ===")
    print("h_t1_checkout ping -c 3 h_hq_sales")
    print("h_t2_checkout ping -c 3 h_hq_sales")
    print("h_wh_inventory ping -c 3 h_hq_inventory")
    print("h_hq_it ping -c 3 h_wh_admin")
    print("h_t1_checkout ping -c 3 h_wh_inventory")
    print("\n=== Security Tests (firewall) ===")
    print("h_t1_wifi_guest ping -c 3 h_hq_sales         # debe FALLAR")
    print("h_hq_sales ping -c 3 h_hq_printer            # debe FALLAR")
    print("h_hq_customer_service ping -c 3 h_hq_finance # debe FALLAR")
    print("h_hq_security_ops ping -c 3 h_hq_camera      # debe FUNCIONAR")
    print("h_hq_sales ping -c 3 h_hq_camera             # debe FALLAR")
    print("\n=== Bandwidth Tests (iperf) ===")
    print("h_hq_sales iperf -s &")
    print("h_t1_checkout iperf -c 10.1.0.40 -t 10       # ~20 Mbps")
    print("h_hq_inventory iperf -s &")
    print("h_wh_inventory iperf -c 10.1.0.200 -t 10     # ~50 Mbps")
    print("h_wh_inventory iperf -s &")
    print("h_t1_checkout iperf -c 10.4.0.10 -t 10       # ~15 Mbps (enlace directo)")
    print("\n=== DHCP Demo ===")
    print("h_hq_sales ip addr flush dev h_hq_sales-eth0")
    print("h_hq_sales dhclient -v h_hq_sales-eth0   # pide IP al router por DHCP")
    print("h_hq_sales ip addr                        # muestra la IP asignada")
    print("=" * 60 + "\n")


if __name__ == '__main__':
    setLogLevel('info')
    build()
