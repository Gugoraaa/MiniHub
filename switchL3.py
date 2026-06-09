from mininet.net import OVSSwitch

class SwitchL3(OVSSwitch):
    def config(self, **params):
        super(SwitchL3, self).config(**params)

        self.cmd('sysctl -w net.ipv4.ip_forward=1')
        self.cmd('sysctl -w net.ipv4.conf.all.rp_filter=0')
        self.cmd('sysctl -w net.ipv4.conf.default.rp_filter=0')

        self.cmd('iptables -P FORWARD ACCEPT')
        self.cmd('iptables -F FORWARD')

    def terminate(self):
        self.cmd('pkill -f dhcrelay > /dev/null 2>&1')
        super(SwitchL3, self).terminate()