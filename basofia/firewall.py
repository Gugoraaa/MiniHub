RED    = '\033[91m'
YELLOW = '\033[93m'
BOLD   = '\033[1m'
RESET  = '\033[0m'


class Firewall:
    # subredes de servicios sensibles de HQ
    HQ_PRINTERS = '10.1.1.96/27'
    HQ_CAMERAS  = '10.1.1.64/27'
    HQ_FINANCE  = '10.1.0.160/27'
    HQ_IT       = '10.1.0.0/27'
    HQ_MGMT     = '10.1.0.96/27'
    HQ_SECOPS   = '10.1.0.64/27'
    HQ_SALES    = '10.1.0.32/27'
    HQ_HR       = '10.1.0.128/27'
    HQ_CUSTSVC  = '10.1.1.0/27'

    def apply(self, routers):
        rhq = routers['r_hq']

        # verifica que iptables funcione en el namespace del router antes de aplicar reglas
        probe = rhq.cmd('iptables -L FORWARD -n 2>&1')
        if 'Chain FORWARD' not in probe:
            print('%s%s[ERROR] iptables no funciona en este sistema:%s %s' % (
                BOLD, RED, RESET, probe.strip().splitlines()[0] if probe.strip() else '(sin salida)'))
            print('%s        Instala iptables:  sudo apt-get install -y iptables%s' % (YELLOW, RESET))
            print('%s        Sin iptables los tests de seguridad NO bloquearan trafico.%s' % (YELLOW, RESET))

        def hq(rule):
            rhq.cmd('iptables ' + rule)

        hq('-P FORWARD ACCEPT')  # politica default ACCEPT; los DROP son especificos

        # los ACCEPT deben ir antes que los DROP para el mismo destino
        hq('-A FORWARD -s %s -d %s -j ACCEPT' % (self.HQ_SECOPS, self.HQ_CAMERAS))  # SecOps puede ver camaras
        hq('-A FORWARD -s %s -d %s -j ACCEPT' % (self.HQ_IT,    self.HQ_FINANCE))   # IT puede ver Finance
        hq('-A FORWARD -s %s -d %s -j ACCEPT' % (self.HQ_MGMT,  self.HQ_FINANCE))   # Mgmt puede ver Finance

        # usuarios comunes no acceden a impresoras HQ
        hq('-A FORWARD -s %s -d %s -j DROP' % (self.HQ_SALES,   self.HQ_PRINTERS))
        hq('-A FORWARD -s %s -d %s -j DROP' % (self.HQ_HR,      self.HQ_PRINTERS))
        hq('-A FORWARD -s %s -d %s -j DROP' % (self.HQ_CUSTSVC, self.HQ_PRINTERS))
        hq('-A FORWARD -d %s -j DROP' % self.HQ_CAMERAS)  # bloquea el resto hacia camaras
        hq('-A FORWARD -d %s -j DROP' % self.HQ_FINANCE)  # bloquea el resto hacia Finance

        # WiFi guest de tiendas no puede acceder a ninguna red interna
        internal = ['10.1.0.0/23', '10.2.1.0/24', '10.3.1.0/24', '10.4.0.0/23']
        for site, router_name, guest_net, local_net in [
            ('t1', 'r_t1', '10.2.0.0/24', '10.2.1.0/24'),
            ('t2', 'r_t2', '10.3.0.0/24', '10.3.1.0/24'),
        ]:
            rt = routers[router_name]
            rt.cmd('iptables -P FORWARD ACCEPT')
            for dst in internal:
                rt.cmd('iptables -A FORWARD -s %s -d %s -j DROP' % (guest_net, dst))
            store_printers = '10.2.1.80/29' if site == 't1' else '10.3.1.80/29'
            store_cameras  = '10.2.1.64/28' if site == 't1' else '10.3.1.64/28'
            checkout       = '10.2.1.0/27'  if site == 't1' else '10.3.1.0/27'
            rt.cmd('iptables -A FORWARD -s %s -d %s -j DROP' % (checkout, store_printers))
            rt.cmd('iptables -A FORWARD -s %s -d %s -j DROP' % (checkout, store_cameras))

        # warehouse: admin no accede a impresoras; shipping no accede a camaras
        rwh = routers['wh_r']
        rwh.cmd('iptables -P FORWARD ACCEPT')
        rwh.cmd('iptables -A FORWARD -s 10.4.0.32/27 -d 10.4.0.144/29 -j DROP')
        rwh.cmd('iptables -A FORWARD -s 10.4.0.96/28 -d 10.4.0.128/28 -j DROP')
