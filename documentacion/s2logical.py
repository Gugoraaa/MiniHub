from mininet.net import Mininet
from mininet.node import OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel

def create_topology():
    net = Mininet(controller=None, switch=OVSSwitch, link=TCLink)

    print("> Adding hosts and switch")
    h1a = net.addHost('h1', ip='10.0.0.1/24')
    h2a = net.addHost('h2', ip='10.0.0.2/24')
    h1b = net.addHost('h3', ip='10.0.1.1/24')
    h2b = net.addHost('h4', ip='10.0.1.2/24')
    s1 = net.addSwitch('s1')

    print("> Creating links (all hosts on the same physical switch)")
    net.addLink(h1a, s1)
    net.addLink(h2a, s1)
    net.addLink(h1b, s1)
    net.addLink(h2b, s1)

    print("> Starting network")
    net.start()

    print("> Running CLI")
    CLI(net)

    print("> Stopping network")
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    create_topology()
