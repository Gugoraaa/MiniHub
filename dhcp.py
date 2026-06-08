import ipaddress


class DHCP:
    YELLOW = '\033[93m'
    RESET  = '\033[0m'

    def _range(self, gw, host_ip, pfx):
        # calcula (start, end, mask) usando la mitad superior de la subred
        # excluye gateway y host representativo para no pisar IPs estaticas
        net = ipaddress.ip_network('%s/%d' % (gw, pfx), strict=False)
        excluded = {ipaddress.ip_address(gw), ipaddress.ip_address(host_ip)}
        pool = [h for h in net.hosts() if h not in excluded]
        if len(pool) < 2:
            return None  # /30: solo 2 IPs utiles, no queda espacio para pool
        mid = len(pool) // 2
        return str(pool[mid]), str(pool[-1]), str(net.netmask)

    def start(self, routers, sites):
        from mininet.log import info

        # verifica que dnsmasq este instalado en el sistema antes de arrancar
        probe = list(routers.values())[0].cmd('which dnsmasq 2>/dev/null').strip()
        if not probe:
            print('%s[WARN] dnsmasq no encontrado — DHCP no disponible.%s' % (self.YELLOW, self.RESET))
            print('       Instala con: sudo apt-get install -y dnsmasq')
            return

        for site in sites:
            r = routers[site.router]
            r.cmd('pkill -f "dnsmasq.*%s" 2>/dev/null; true' % site.name)  # mata instancias previas

            args = [
                'dnsmasq',
                '--no-resolv',        # no usa /etc/resolv.conf del host
                '--no-hosts',         # no usa /etc/hosts del host
                '--bind-interfaces',  # escucha solo en las interfaces declaradas
                '--except-interface=lo',
                '--pid-file=/tmp/dnsmasq-%s.pid' % site.name,
                '--log-facility=/tmp/dnsmasq-%s.log' % site.name,
            ]

            served = 0
            for (hname, halias, vid, gw, hip, pfx, floor) in site.vlans:
                result = self._range(gw, hip, pfx)
                if result is None:
                    continue
                start, end, mask = result
                tag  = 'vid%d' % vid                     # tag por VLAN para separar pools en una sola instancia
                intf = '%s-v%d' % (site.ralias, vid)     # interfaz gateway del router para esta VLAN
                args += [
                    '--interface=%s' % intf,
                    '--dhcp-range=tag:%s,%s,%s,%s,12h' % (tag, start, end, mask),
                    '--dhcp-option=tag:%s,option:router,%s' % (tag, gw),  # gateway por VLAN
                ]
                served += 1

            if served == 0:
                continue

            out = r.cmd(' '.join(args) + ' 2>&1').strip()
            if out:
                print('%s[WARN]%s dnsmasq %s: %s' % (self.YELLOW, self.RESET, site.name, out))
            else:
                info('*** DHCP activo en %s (%d VLANs)\n' % (site.router, served))
