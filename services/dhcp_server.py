class DHCPServer:
    """
    Servidor DHCP reutilizable usando dnsmasq con archivo .conf externo.
    """

    def __init__(
        self,
        net,
        name,
        ip_cidr,
        gateway,
        conf_path,
        pid_path,
        lease_path,
        log_path
    ):
        self.net = net
        self.name = name
        self.ip_cidr = ip_cidr
        self.gateway = gateway
        self.conf_path = conf_path
        self.pid_path = pid_path
        self.lease_path = lease_path
        self.log_path = log_path

        self.host = net.addHost(
            name,
            ip=ip_cidr,
            defaultRoute=f'via {gateway}'
        )

    def start(self):
        # Matar cualquier instancia previa que tenga el puerto 67 tomado
        self.host.cmd('killall dnsmasq 2>/dev/null || true')
        self.host.cmd(f'rm -f {self.pid_path} {self.lease_path} {self.log_path}')

        self.host.cmd(
            f'dnsmasq '
            f'--conf-file={self.conf_path} '
            f'--pid-file={self.pid_path} '
            f'--dhcp-leasefile={self.lease_path} '
            f'--log-dhcp '
            f'--log-facility={self.log_path}'
        )

    def stop(self):
        self.host.cmd(f'kill $(cat {self.pid_path}) 2>/dev/null || true')
        self.host.cmd('killall dnsmasq 2>/dev/null || true')