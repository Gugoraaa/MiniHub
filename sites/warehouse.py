from ipaddress import ip_network
from router import Router




class Warehouse:
    """
    Warehouse / Almacén Santa Catarina site.

    Main block: 10.4.0.0/23
    WAN default link suggested by the addressing plan: HQ <-> Almacén = 10.0.3.0/30
    Local WAN IP suggested for the warehouse router: 10.0.3.2/30

    Usage in a master file:
        wh = Warehouse(static_hosts=True, full_hosts=False)
        wh.build(net)
        net.start()
        wh.configure()
    """

    VLANS = {
        70:  {'label': 'inventory_control', 'short': 'ic',  'subnet': '10.4.0.0/27',    'gateway': '10.4.0.1',   'real_hosts': 15},
        40:  {'label': 'warehouse_office',  'short': 'wo',  'subnet': '10.4.0.32/27',   'gateway': '10.4.0.33',  'real_hosts': 12},
        150: {'label': 'receiving_area',    'short': 'ra',  'subnet': '10.4.0.64/27',   'gateway': '10.4.0.65',  'real_hosts': 10},
        160: {'label': 'shipping_area',     'short': 'sa',  'subnet': '10.4.0.96/28',   'gateway': '10.4.0.97',  'real_hosts': 9},
        30:  {'label': 'security',          'short': 'sec', 'subnet': '10.4.0.112/28',  'gateway': '10.4.0.113', 'real_hosts': 9},
        100: {'label': 'cameras',           'short': 'cam', 'subnet': '10.4.0.128/28',  'gateway': '10.4.0.129', 'real_hosts': 8},
        110: {'label': 'printers',          'short': 'prt', 'subnet': '10.4.0.144/29',  'gateway': '10.4.0.145', 'real_hosts': 4},
        120: {'label': 'phones',            'short': 'phn', 'subnet': '10.4.0.152/30',  'gateway': '10.4.0.153', 'real_hosts': 1},
    }

    def __init__(self, prefix='wh', static_hosts=True, full_hosts=False):
        """
        prefix: avoids name collisions when this site is imported with HQ/stores.
        static_hosts: True assigns fixed IPs; False leaves endpoints without IP for DHCP.
        full_hosts: False creates one representative node per VLAN; True creates all real hosts from the table.
        """
        self.prefix = prefix
        self.static_hosts = static_hosts
        self.full_hosts = full_hosts

        self.core = None
        self.distribution = None
        self.wan_router = None

        self.access_switches = {}
        self.hosts = {}
        self.links = []

        self.access_host_ports = {}
        self.access_uplink_ports = {}
        self.distribution_trunk_ports = []
        self.core_trunk_ports = []
        self.core_to_router_intf = None
        self.router_to_core_intf = None
        self.wan_intf = None
        self.wan_ip = None
        self.remote_wan_ip = None

    def build(self, net):
        """Create Mininet nodes and links. Call before net.start()."""
        self._add_core_and_distribution(net)
        self._add_access_switches(net)
        self._add_vlan_hosts(net)
        self._connect_lan(net)
        return self

    def configure(self):
        """Apply OVS VLAN tags, L3 gateway interfaces, and router routes. Call after net.start()."""
        self._configure_access_ports()
        self._configure_trunks()
        self._configure_vlan_gateways()
        self._configure_router_to_core()
        return self

    def connect_wan(self, net, remote_router, local_ip='10.0.3.2/30', remote_ip='10.0.3.1'):
        """
        Connect the warehouse WAN router to an external router.
        Call before net.start() from the master topology.
        """
        link = net.addLink(self.wan_router, remote_router)
        self.wan_intf = link.intf1.name if link.intf1.node == self.wan_router else link.intf2.name
        self.wan_ip = local_ip
        self.remote_wan_ip = remote_ip
        self.links.append(link)
        return link

    def configure_wan(self, default_via='10.0.3.1'):
        """Configure the WAN interface after net.start(), only if connect_wan() was used."""
        if self.wan_intf and self.wan_ip:
            self.wan_router.cmd(f'ip addr flush dev {self.wan_intf}')
            self.wan_router.cmd(f'ip addr add {self.wan_ip} dev {self.wan_intf}')
            self.wan_router.cmd(f'ip link set {self.wan_intf} up')
            self.wan_router.cmd(f'ip route replace default via {default_via}')
        return self

    def add_route_to(self, destination_cidr, via=None):
        """Add static route on the warehouse router to reach another site."""
        next_hop = via or self.remote_wan_ip
        if not next_hop:
            raise ValueError('No next-hop provided. Use via="x.x.x.x" or call connect_wan() first.')
        self.wan_router.cmd(f'ip route replace {destination_cidr} via {next_hop}')
        return self

    def gateways(self):
        """Return VLAN gateway IPs for DHCP or documentation generated elsewhere."""
        return {vlan: data['gateway'] for vlan, data in self.VLANS.items()}

    def subnets(self):
        """Return VLAN subnets for DHCP scopes, firewall rules, or reports generated elsewhere."""
        return {vlan: data['subnet'] for vlan, data in self.VLANS.items()}

    def _add_core_and_distribution(self, net):
        self.core = net.addSwitch('s1', failMode='standalone')         # wh core
        self.distribution = net.addSwitch('s2', failMode='standalone') # wh distribution
        self.wan_router = net.addHost(f'{self.prefix}_r', cls=Router, ip=None)

    # s3-s10: access switches, one per VLAN (wh_acc_v70..v120), ordered by VLANS dict
    _ACCESS_SW_NAMES = {
        70:  's3',   # wh acc inventory_control
        40:  's4',   # wh acc warehouse_office
        150: 's5',   # wh acc receiving_area
        160: 's6',   # wh acc shipping_area
        30:  's7',   # wh acc security
        100: 's8',   # wh acc cameras
        110: 's9',   # wh acc printers
        120: 's10',  # wh acc phones
    }

    def _add_access_switches(self, net):
        for vlan_id in self.VLANS:
            sw_name = self._ACCESS_SW_NAMES[vlan_id]
            self.access_switches[vlan_id] = net.addSwitch(sw_name, failMode='standalone')
            self.access_host_ports[vlan_id] = []
            self.access_uplink_ports[vlan_id] = None

    def _add_vlan_hosts(self, net):
        for vlan_id, data in self.VLANS.items():
            host_count = data['real_hosts'] if self.full_hosts else 1
            network = ip_network(data['subnet'])
            gateway = data['gateway']
            prefix_len = network.prefixlen
            usable_ips = [str(ip) for ip in network.hosts() if str(ip) != gateway]

            self.hosts[vlan_id] = []
            for i in range(1, host_count + 1):
                host_name = f"{self.prefix}_{data['short']}_{i:02d}"
                if self.static_hosts:
                    ip_addr = f'{usable_ips[i - 1]}/{prefix_len}'
                    default_route = f'via {gateway}'
                else:
                    ip_addr = None
                    default_route = None
                self.hosts[vlan_id].append(net.addHost(host_name, ip=ip_addr, defaultRoute=default_route))

    def _connect_lan(self, net):
        core_dist_link = net.addLink(self.core, self.distribution)
        self.core_trunk_ports.append(core_dist_link.intf1.name)
        self.distribution_trunk_ports.append(core_dist_link.intf2.name)
        self.links.append(core_dist_link)

        core_router_link = net.addLink(self.core, self.wan_router)
        self.core_to_router_intf = core_router_link.intf1.name
        self.router_to_core_intf = core_router_link.intf2.name
        self.links.append(core_router_link)

        for vlan_id, sw in self.access_switches.items():
            uplink = net.addLink(sw, self.distribution)
            self.access_uplink_ports[vlan_id] = uplink.intf1.name
            self.distribution_trunk_ports.append(uplink.intf2.name)
            self.links.append(uplink)

            for host in self.hosts[vlan_id]:
                host_link = net.addLink(host, sw)
                self.access_host_ports[vlan_id].append(host_link.intf2.name)
                self.links.append(host_link)

    def _configure_access_ports(self):
        for vlan_id, ports in self.access_host_ports.items():
            sw = self.access_switches[vlan_id]
            for port in ports:
                sw.cmd(f'ovs-vsctl set port {port} tag={vlan_id}')

    def _configure_trunks(self):
        allowed = ','.join(str(vlan) for vlan in self.VLANS.keys())

        for vlan_id, port in self.access_uplink_ports.items():
            self.access_switches[vlan_id].cmd(f'ovs-vsctl set port {port} trunks={allowed}')

        for port in self.distribution_trunk_ports:
            self.distribution.cmd(f'ovs-vsctl set port {port} trunks={allowed}')

        for port in self.core_trunk_ports:
            self.core.cmd(f'ovs-vsctl set port {port} trunks={allowed}')

    def _configure_vlan_gateways(self):
        self.core.cmd('sysctl -w net.ipv4.ip_forward=1')
        for vlan_id, data in self.VLANS.items():
            vlan_intf = f'{self.prefix}_vlan{vlan_id}'
            prefix_len = ip_network(data['subnet']).prefixlen
            gateway_cidr = f"{data['gateway']}/{prefix_len}"
            self.core.cmd(
                f'ovs-vsctl --may-exist add-port {self.core.name} {vlan_intf} '
                f'tag={vlan_id} -- set interface {vlan_intf} type=internal'
            )
            self.core.cmd(f'ip addr flush dev {vlan_intf}')
            self.core.cmd(f'ip addr add {gateway_cidr} dev {vlan_intf}')
            self.core.cmd(f'ip link set {vlan_intf} up')

    def _configure_router_to_core(self):
        self.core.cmd(f'ip addr flush dev {self.core_to_router_intf}')
        self.core.cmd(f'ip addr add 10.4.1.253/30 dev {self.core_to_router_intf}')
        self.core.cmd(f'ip link set {self.core_to_router_intf} up')

        self.wan_router.cmd(f'ip addr flush dev {self.router_to_core_intf}')
        self.wan_router.cmd(f'ip addr add 10.4.1.254/30 dev {self.router_to_core_intf}')
        self.wan_router.cmd(f'ip link set {self.router_to_core_intf} up')

        self.core.cmd('ip route replace default via 10.4.1.254')
        self.wan_router.cmd('ip route replace 10.4.0.0/23 via 10.4.1.253')
