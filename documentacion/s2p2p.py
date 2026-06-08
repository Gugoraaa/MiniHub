from mininet.net import Mininet
from mininet.node import OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel

def create_topology():
    net = Mininet(controller=None, switch=OVSSwitch, link=TCLink)

    print("> Adding hosts")
    h1 = net.addHost('h1')
    h2 = net.addHost('h2')

    print("> Creating constrained link (10 Mbps, 5ms delay, 10% loss)")
    net.addLink(h1, h2, bw=10, delay='5ms', loss=10)

    print("> Starting network")
    net.start()

    print("> Running CLI")
    CLI(net)

    print("> Stopping network")
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    create_topology()
