from .base import Site
from utils import _ifn


class HQ(Site):
    name   = 'hq'
    router = 'r_hq'
    ralias = 'rhq'
    core   = 's_hq_core'
    calias = 'shqc'
    floors = {
        1: ('s_hq_floor1', 'shqf1'),
        2: ('s_hq_floor2', 'shqf2'),
        3: ('s_hq_floor3', 'shqf3'),
        4: ('s_hq_floor4', 'shqf4'),
    }
    block = '10.1.0.0/23'
    vlans = [
        #  host                     alias    vid   gateway        host_ip        pfx  floor
        ('h_hq_it',              'hhqit',  10,  '10.1.0.1',   '10.1.0.10',   27,  4),
        ('h_hq_sales',           'hhqsa',  20,  '10.1.0.33',  '10.1.0.40',   27,  2),
        ('h_hq_security_ops',    'hhqso',  30,  '10.1.0.65',  '10.1.0.70',   27,  1),
        ('h_hq_management',      'hhqmg',  40,  '10.1.0.97',  '10.1.0.100',  27,  3),
        ('h_hq_hr',              'hhqhr',  50,  '10.1.0.129', '10.1.0.130',  27,  3),
        ('h_hq_finance',         'hhqfi',  60,  '10.1.0.161', '10.1.0.170',  27,  4),
        ('h_hq_inventory',       'hhqiv',  70,  '10.1.0.193', '10.1.0.200',  27,  1),
        ('h_hq_customer_service','hhqcs',  80,  '10.1.1.1',   '10.1.1.10',   27,  2),
        ('h_hq_procurement',     'hhqpc',  90,  '10.1.1.33',  '10.1.1.40',   27,  4),
        ('h_hq_camera',          'hhqcm', 100,  '10.1.1.65',  '10.1.1.70',   27,  1),
        ('h_hq_printer',         'hhqpr', 110,  '10.1.1.97',  '10.1.1.100',  27,  4),
        ('h_hq_phone',           'hhqpn', 120,  '10.1.1.129', '10.1.1.130',  27,  2),
    ]

    def build(self, net, router_cls):
        r = super().build(net, router_cls)
        # nodo representativo del servidor DHCP centralizado, conectado al piso 4
        dhcp = net.addHost('dhcp_hq', ip='10.1.0.11/27', defaultRoute='via 10.1.0.1')
        net.addLink(dhcp, net.get('s_hq_floor4'),
                    intfName1=_ifn('dhcphq'), intfName2=_ifn('shqf4'))
        return r
