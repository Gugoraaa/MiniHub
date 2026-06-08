from mininet.node import Node


# host Mininet que actua como router: habilita ip_forward y ajusta ARP/rp_filter
class Router(Node):
    def config(self, **params):
        super().config(**params)
        self.cmd('sysctl -w net.ipv4.ip_forward=1')
        # rp_filter=0 global; tambien se zeroes por interfaz despues de start()
        # porque el valor efectivo es max(conf.all, conf.<intf>)
        self.cmd('sysctl -w net.ipv4.conf.all.rp_filter=0')
        self.cmd('sysctl -w net.ipv4.conf.default.rp_filter=0')
        # evita ARP flux: cada interfaz responde solo por su propia IP
        self.cmd('sysctl -w net.ipv4.conf.all.arp_ignore=1')
        self.cmd('sysctl -w net.ipv4.conf.all.arp_announce=2')

    def terminate(self):
        self.cmd('sysctl -w net.ipv4.ip_forward=0')
        super().terminate()
