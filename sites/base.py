from utils import _ifn, _dpid


class Site:
    name   = ''
    router = ''
    ralias = ''
    core   = ''
    calias = ''
    floors = {}
    block  = ''
    vlans  = []

    def build(self, net, router_cls):
        r = net.addHost(self.router, cls=router_cls)

        # standalone: el switch opera sin controlador SDN
        core = net.addSwitch(self.core, failMode='standalone', dpid=_dpid())
        floor_sw = {}
        for fnum, (fname, falias) in self.floors.items():
            sw = net.addSwitch(fname, failMode='standalone', dpid=_dpid())
            floor_sw[fnum] = (sw, falias)
            net.addLink(sw, core, intfName1=_ifn(falias), intfName2=_ifn(self.calias))  # piso -> core

        for (hname, halias, vid, gw, hip, pfx, floor) in self.vlans:
            host = net.addHost(hname, ip='%s/%d' % (hip, pfx), defaultRoute='via %s' % gw)
            fsw, falias = floor_sw[floor]
            net.addLink(host, fsw, intfName1=_ifn(halias), intfName2=_ifn(falias))  # host -> piso
            # una interfaz del router por VLAN; la IP gateway se asigna en Topology despues de net.start()
            net.addLink(r, core,
                        intfName1='%s-v%d' % (self.ralias, vid),
                        intfName2=_ifn(self.calias))

        return r
