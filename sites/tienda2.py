from .base import Site


class Tienda2(Site):
    name   = 't2'
    router = 'r_t2'
    ralias = 'rt2'
    core   = 's_t2_core'
    calias = 'st2c'
    floors = {
        1: ('s_t2_floor1', 'st2f1'),
        2: ('s_t2_floor2', 'st2f2'),
    }
    block = '10.3.0.0/23'
    vlans = [
        #  host              alias    vid   gateway       host_ip       pfx  floor
        ('h_t2_wifi_guest', 'ht2wg', 130, '10.3.0.1',  '10.3.0.10',  24,  2),
        ('h_t2_checkout',   'ht2ck', 140, '10.3.1.1',  '10.3.1.10',  27,  1),
        ('h_t2_admin',      'ht2ad',  40, '10.3.1.33', '10.3.1.34',  28,  2),
        ('h_t2_security',   'ht2se',  30, '10.3.1.49', '10.3.1.50',  28,  1),
        ('h_t2_camera',     'ht2cm', 100, '10.3.1.65', '10.3.1.66',  28,  1),
        ('h_t2_printer',    'ht2pr', 110, '10.3.1.81', '10.3.1.82',  29,  2),
        ('h_t2_phone',      'ht2pn', 120, '10.3.1.89', '10.3.1.90',  30,  2),
    ]
