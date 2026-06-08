_if_count = {}  # contador por alias para garantizar unicidad de nombre
_sw_dpid  = 0   # contador global de datapath IDs


def _ifn(alias):
    # IFNAMSIZ: 15 chars max; alias corto + contador se mantiene bajo el limite
    n = _if_count.get(alias, 0)
    _if_count[alias] = n + 1
    return '%s-%d' % (alias, n)


def _dpid():
    # OVS no puede derivar un datapath ID estable desde nombres descriptivos de nodos
    global _sw_dpid
    _sw_dpid += 1
    return '%016x' % _sw_dpid
