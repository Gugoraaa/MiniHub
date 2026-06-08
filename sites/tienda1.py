from .base import Site


class Tienda1(Site):
    name   = 't1'
    router = 'r_t1'
    ralias = 'rt1'
    core   = 's_t1_core'
    calias = 'st1c'
    floors = {
        1: ('s_t1_floor1', 'st1f1'),
        2: ('s_t1_floor2', 'st1f2'),
    }
    block = '10.2.0.0/23'
    vlans = [
        #  host              alias    vid   gateway       host_ip       pfx  floor
        ('h_t1_wifi_guest', 'ht1wg', 130, '10.2.0.1',  '10.2.0.10',  24,  2),
        ('h_t1_checkout',   'ht1ck', 140, '10.2.1.1',  '10.2.1.10',  27,  1),
        ('h_t1_admin',      'ht1ad',  40, '10.2.1.33', '10.2.1.34',  28,  2),
        ('h_t1_security',   'ht1se',  30, '10.2.1.49', '10.2.1.50',  28,  1),
        ('h_t1_camera',     'ht1cm', 100, '10.2.1.65', '10.2.1.66',  28,  1),
        ('h_t1_printer',    'ht1pr', 110, '10.2.1.81', '10.2.1.82',  29,  2),
        ('h_t1_phone',      'ht1pn', 120, '10.2.1.89', '10.2.1.90',  30,  2),
    ]
