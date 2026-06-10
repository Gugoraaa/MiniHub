# Explicacion de HQ

Este documento describe HQ en `sites/hq.py`. Los hosts representativos principales siguen usando IPs estaticas para no romper las pruebas existentes, y ademas se agrego DHCP como servicio de HQ con clientes dedicados de prueba.

## Topologia

HQ tiene esta estructura:

```text
hosts de usuario
    -> switches access s1, s2, s3, s4
    -> switch distribution s0
    -> switch L3 s5
    -> router WAN hqr
```

El switch L3 `s5` tambien conecta servicios internos:

```text
s5 -> hdns  DNS  10.1.0.10
s5 -> hweb  HTTP 10.1.0.11
s5 -> dhcphq DHCP 192.168.101.10
```

Los hosts principales tienen IP estatica desde `net.addHost(...)`. Los clientes `dh10`, `dh60` y `dh100` existen solo para probar DHCP sin mover esas IPs estaticas.

## Archivos de HQ

- `sites/hq.py`: topologia, VLANs, SVIs, rutas, DNS y HTTP.
- `hq/site.conf`: configuracion de `dnsmasq` para DNS.
- `hq/records.txt`: nombres locales como `web.hq.local`.
- `hq/resolv.conf`: archivo que fuerza a los hosts a usar `10.1.0.10` como DNS.
- `tmp/dhcp_hq.conf`: pools DHCP por VLAN para los clientes de prueba.
- `master_wan.py`: runner que levanta HQ y abre la CLI de Mininet.
- `clean.sh`: limpieza previa de DNS, HTTP y Mininet.

## Imports

```python
import os

from router import Router
from services.dhcp_server import DHCPServer
from switchL3 import SwitchL3
```

`os` se usa para construir rutas absolutas hacia archivos de la carpeta `hq`.

`Router` crea el router WAN `hqr`.

`DHCPServer` crea el host `dhcphq` y levanta `dnsmasq` como servidor DHCP.

`SwitchL3` crea el switch multilayer `s5`, que puede rutear entre VLANs usando SVIs.

## VLANs

```python
VLANS = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120]
DHCPVLAN = 998
WANVLAN = 999
```

`VLANS` son las VLANs de usuarios y servicios internos.

`DHCPVLAN = 998` es una VLAN de servicio para conectar `s5` con `dhcphq`.

`WANVLAN = 999` es la VLAN del enlace de transito entre `s5` y `hqr`.

## SVIGATEWAYS

```python
SVIGATEWAYS = {
    10: '10.1.0.1/27',
    20: '10.1.0.33/27',
    ...
    120: '10.1.1.129/27',
}
```

Cada entrada define el gateway de una VLAN. Por ejemplo:

- VLAN 10 usa `10.1.0.1/27`.
- VLAN 20 usa `10.1.0.33/27`.
- VLAN 120 usa `10.1.1.129/27`.

En `s5`, cada gateway se implementa como una SVI. Una SVI es una interfaz virtual asociada a una VLAN. Sirve para que el switch L3 pueda ser la puerta de enlace de esa VLAN y enrutar hacia otras VLANs.

## Estado de la clase

```python
self.gateway = None
self.mls = None
self.hdns = None
self.hweb = None
self.dhcp = None
self.dnsclients = []
```

- `gateway`: referencia al router WAN `hqr`.
- `mls`: referencia al switch L3 `s5`.
- `hdns`: referencia al servidor DNS.
- `hweb`: referencia al servidor HTTP.
- `dhcp`: referencia al servidor DHCP `dhcphq`.
- `dnsclients`: lista de hosts que deben usar el DNS local de HQ.

## hqpath

```python
def hqpath(self, filename):
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', 'hq', filename)
    )
```

Esta funcion devuelve una ruta absoluta hacia archivos dentro de `MiniHub/hq`.

Se usa principalmente para montar `hq/resolv.conf` en los hosts, sin depender de la carpeta desde donde se ejecuto el script.

## build(net)

`build(net)` crea nodos y enlaces. No configura todavia VLANs, IPs de servicios ni rutas avanzadas.

### Router WAN

```python
self.gateway = net.addHost('hqr', cls=Router, ip=None)
```

Crea el router WAN. Se usa `ip=None` porque la IP del enlace WAN se configura despues en `configure()`.

### Switches

```python
hdist = net.addSwitch('s0', failMode='standalone')
hf1 = net.addSwitch('s1', failMode='standalone')
hf2 = net.addSwitch('s2', failMode='standalone')
hf3 = net.addSwitch('s3', failMode='standalone')
hf4 = net.addSwitch('s4', failMode='standalone')
self.mls = net.addSwitch('s5', cls=SwitchL3, failMode='standalone')
```

`s1` a `s4` son switches access.

`s0` es el switch de distribucion.

`s5` es el switch capa 3.

`failMode='standalone'` permite forwarding sin controlador externo.

### Hosts con IP estatica

Los hosts representativos se crean con IP y gateway desde el inicio:

```python
hit = net.addHost('hit', ip='10.1.0.2/27', defaultRoute='via 10.1.0.1')
hsales = net.addHost('hsales', ip='10.1.0.34/27', defaultRoute='via 10.1.0.33')
hsec = net.addHost('hsec', ip='10.1.0.66/27', defaultRoute='via 10.1.0.65')
```

Esto se repite para los 12 hosts:

- `hit`: VLAN 10, `10.1.0.2/27`, gateway `10.1.0.1`.
- `hsales`: VLAN 20, `10.1.0.34/27`, gateway `10.1.0.33`.
- `hsec`: VLAN 30, `10.1.0.66/27`, gateway `10.1.0.65`.
- `hmgmt`: VLAN 40, `10.1.0.98/27`, gateway `10.1.0.97`.
- `hhr`: VLAN 50, `10.1.0.130/27`, gateway `10.1.0.129`.
- `hfin`: VLAN 60, `10.1.0.162/27`, gateway `10.1.0.161`.
- `hinv`: VLAN 70, `10.1.0.194/27`, gateway `10.1.0.193`.
- `hcust`: VLAN 80, `10.1.1.2/27`, gateway `10.1.1.1`.
- `hpurch`: VLAN 90, `10.1.1.34/27`, gateway `10.1.1.33`.
- `hcam`: VLAN 100, `10.1.1.66/27`, gateway `10.1.1.65`.
- `hprint`: VLAN 110, `10.1.1.98/27`, gateway `10.1.1.97`.
- `hphone`: VLAN 120, `10.1.1.130/27`, gateway `10.1.1.129`.

### Servidores internos

```python
self.hdns = net.addHost('hdns', ip=None)
self.hweb = net.addHost('hweb', ip=None)
self.dhcp = DHCPServer(...)
```

`hdns` recibe IP despues: `10.1.0.10/27`.

`hweb` recibe IP despues: `10.1.0.11/27`.

`dhcphq` usa `192.168.101.10/24` en una VLAN de servicio.

`hdns` y `hweb` viven en VLAN 10. `dhcphq` vive en VLAN 998.

### Clientes DHCP de prueba

```python
dh10 = net.addHost('dh10', ip=None)
dh60 = net.addHost('dh60', ip=None)
dh100 = net.addHost('dh100', ip=None)
```

Estos hosts no reemplazan a `hit`, `hfin` ni `hcam`. Solo sirven para probar que DHCP funciona:

- `dh10` esta en VLAN 10.
- `dh60` esta en VLAN 60.
- `dh100` esta en VLAN 100.

### dnsclients

```python
self.dnsclients = [
    hit, hsales, hsec,
    hmgmt, hhr, hfin,
    hinv, hcust, hpurch,
    hcam, hprint, hphone,
    self.hweb,
]
```

Esta lista contiene los hosts donde se monta `hq/resolv.conf`. Eso hace que usen el DNS `10.1.0.10`.

### Enlaces

Los hosts se conectan a access switches:

```python
net.addLink(hit, hf1, port2=1)
net.addLink(hsales, hf1, port2=2)
net.addLink(hsec, hf1, port2=3)
```

Los access switches suben a distribution:

```python
net.addLink(hf1, hdist, port1=10, port2=1)
...
net.addLink(hf4, hdist, port1=10, port2=4)
```

Distribution sube al L3:

```python
net.addLink(hdist, self.mls, port1=24, port2=1)
```

El L3 conecta WAN, DNS y HTTP:

```python
net.addLink(self.mls, self.gateway, port1=2, intfName2='hqr-eth0')
net.addLink(self.mls, self.hdns, port1=3, intfName2='hdns-eth0')
net.addLink(self.mls, self.hweb, port1=4, intfName2='hweb-eth0')
net.addLink(self.mls, self.dhcp.host, port1=5, intfName2='dhcphq-eth0')
```

## createsvi

```python
def createsvi(self, vlanid, gatewaycidr, intfname=None):
    intfname = intfname or f'hqvlan{vlanid}'
```

Si no se pasa nombre, la SVI se llama `hqvlan10`, `hqvlan20`, etc.

Despues ejecuta:

```bash
ovs-vsctl --may-exist add-port s5 hqvlan10 tag=10 -- set interface hqvlan10 type=internal
ip addr flush dev hqvlan10
ip addr add 10.1.0.1/27 dev hqvlan10
ip link set hqvlan10 up
```

Esto crea una interfaz interna en `s5`, le asigna una VLAN y le pone IP. Esa IP es el gateway de la VLAN.

## DNS

### configuredns

```python
self.mls.cmd('ovs-vsctl set port s5-eth3 tag=10')
```

El puerto hacia `hdns` queda en VLAN 10.

```python
self.hdns.setIP('10.1.0.10/27', intf='hdns-eth0')
self.hdns.setDefaultRoute('via 10.1.0.1')
```

`hdns` queda como servidor DNS en `10.1.0.10`.

Luego se arranca `dnsmasq`:

```python
dnsmasq -d --conf-file=./hq/site.conf --pid-file=/tmp/dnsmasq-hq.pid &
```

Este comando levanta DNS usando `hq/site.conf`. El `&` deja el proceso corriendo mientras la topologia sigue activa.

### hq/site.conf

```conf
no-hosts
no-resolv
domain-needed
local=/hq.local/
log-queries
addn-hosts=./hq/records.txt
except-interface=lo
```

`addn-hosts=./hq/records.txt` carga los registros DNS de HQ.

`local=/hq.local/` declara `hq.local` como zona local.

`no-resolv` evita usar DNS externos.

### hq/records.txt

```text
10.1.0.10 dns.hq.local dns.local
10.1.0.11 web.hq.local www.hq.local
10.1.0.1 gateway.it.hq.local
10.1.0.33 gateway.sales.hq.local
10.1.0.161 gateway.finance.hq.local
10.1.1.65 gateway.camera.hq.local
10.1.2.2 router.hq.local hqr.hq.local
```

Este archivo permite resolver nombres internos. Por ejemplo:

```bash
hit nslookup web.hq.local
```

debe resolver a `10.1.0.11`.

### mountresolv

```python
source = self.hqpath('resolv.conf')
for host in self.dnsclients:
    host.cmd('umount /etc/resolv.conf 2>/dev/null || true')
    host.cmd('touch /etc/resolv.conf')
    host.cmd(f'mount --bind {source} /etc/resolv.conf')
```

Monta `hq/resolv.conf` en cada cliente.

`hq/resolv.conf` contiene:

```conf
nameserver 10.1.0.10
```

Asi, los hosts usan el DNS local de HQ.

## HTTP

### configurehttp

```python
self.mls.cmd('ovs-vsctl set port s5-eth4 tag=10')
```

El puerto hacia `hweb` queda en VLAN 10.

```python
self.hweb.setIP('10.1.0.11/27', intf='hweb-eth0')
self.hweb.setDefaultRoute('via 10.1.0.1')
```

`hweb` queda como servidor HTTP en `10.1.0.11`.

Luego se crea la pagina:

```bash
mkdir -p /tmp/hq-web
printf '<h1>MiniHub HQ Web Server</h1>' > /tmp/hq-web/index.html
```

Y se levanta HTTP:

```bash
cd /tmp/hq-web && python3 -m http.server 80
```

Como `web.hq.local` apunta a `10.1.0.11`, esta prueba valida DNS y HTTP juntos:

```bash
hit curl http://web.hq.local
```

## DHCP

### configuredhcp

`dhcphq` se conecta directo a `s5-eth5`. Ese puerto queda en VLAN 998:

```python
self.mls.cmd(f'ovs-vsctl set port s5-eth5 tag={self.DHCPVLAN}')
self.createsvi(self.DHCPVLAN, '192.168.101.254/24', intfname='hqdhcp')
```

La SVI `hqdhcp` es el gateway del servidor DHCP.

```python
self.dhcp.host.setIP('192.168.101.10/24', intf='dhcphq-eth0')
self.dhcp.host.cmd('ip route replace default via 192.168.101.254')
self.dhcp.start()
```

`self.dhcp.start()` arranca `dnsmasq` usando `tmp/dhcp_hq.conf`.

Como el servidor DHCP esta en VLAN 998 y los clientes estan en VLANs de usuarios, `s5` corre `dhcrelay`:

```python
dhcrelay -4 -i hqvlan10 ... -i hqvlan120 -i hqdhcp 192.168.101.10
```

El relay escucha solicitudes DHCP en las SVIs de usuario y las reenvia al servidor `192.168.101.10`.

### tmp/dhcp_hq.conf

Este archivo define los pools de HQ. Cada pool entrega:

- rango de IP;
- gateway de su VLAN;
- DNS `10.1.0.10`.

Ejemplo VLAN 10:

```conf
dhcp-range=set:vlan10,10.1.0.12,10.1.0.30,255.255.255.224,12h
dhcp-option=tag:vlan10,option:router,10.1.0.1
dhcp-option=tag:vlan10,option:dns-server,10.1.0.10
```

Se usa `10.1.0.10` como DNS porque ese es `hdns`, y solo el DNS local conoce nombres como `web.hq.local`.

## configure()

`configure()` corre despues de `net.start()`.

Primero activa forwarding en `s5`:

```bash
sysctl -w net.ipv4.ip_forward=1
iptables -P FORWARD ACCEPT
iptables -F FORWARD
```

Luego configura los puertos access. Ejemplo en `s1`:

```python
s1-eth1 -> VLAN 10
s1-eth2 -> VLAN 20
s1-eth3 -> VLAN 30
```

Despues configura trunks:

- Access switches hacia `s0`.
- `s0` hacia access switches.
- `s0` hacia `s5`.
- `s5-eth1` como trunk hacia `s0`.

Luego crea todas las SVIs usando `SVIGATEWAYS`.

Despues configura WAN:

```python
s5-eth2 -> VLAN 999
hqwan = 10.1.2.1/30
hqr-eth0 = 10.1.2.2/30
```

Luego levanta servicios:

```python
self.configuredns()
self.configurehttp()
self.configuredhcp()
```

Finalmente configura rutas:

```python
self.mls.cmd('ip route replace default via 10.1.2.2')
self.gateway.cmd('ip route replace 10.1.0.0/23 via 10.1.2.1')
self.gateway.cmd('ip route replace 192.168.101.0/24 via 10.1.2.1')
```

`s5` manda trafico desconocido a `hqr`.

`hqr` sabe regresar hacia las redes internas de HQ.

## master_wan.py

`master_wan.py`:

1. Cambia al directorio `MiniHub`.
2. Ejecuta `clean.sh`.
3. Crea `Mininet`.
4. Crea `HQSite`.
5. Ejecuta `hq.build(net)`.
6. Ejecuta `net.start()`.
7. Ejecuta `hq.configure()`.
8. Imprime pruebas sugeridas.
9. Abre `CLI(net)`.
10. Al salir, ejecuta `net.stop()`.

## clean.sh

`clean.sh` limpia procesos de HQ antes de una corrida:

```bash
pkill -f 'dnsmasq.*hq/site.conf'
pkill -f 'dnsmasq.*tmp/dhcp_hq.conf'
pkill -f 'dhcrelay.*192.168.101.10'
pkill -f 'dhclient.*dh10-eth0'
pkill -f 'dhclient.*dh60-eth0'
pkill -f 'dhclient.*dh100-eth0'
pkill -f 'python3 -m http.server 80'
rm -f /tmp/dnsmasq-hq.pid /tmp/dnsmasq-hq.log
rm -f /tmp/http-hq.pid /tmp/http-hq.log
rm -f tmp/dhcp_hq.pid tmp/dhcp_hq.leases tmp/dhcp_hq.log
rm -rf /tmp/hq-web
mn -c
```

## Pruebas

Dentro de Mininet:

```bash
hit ping -c 3 10.1.0.1
hit ping -c 3 hsales
hit ping -c 3 hfin
hfin ping -c 3 hcam
hsales ping -c 3 hphone
s5 ping -c 3 10.1.2.2
hqr ping -c 3 10.1.2.1
hit ping -c 3 10.1.2.2
hit ping -c 3 10.1.0.10
hit nslookup web.hq.local
hit curl http://web.hq.local
dh10 dhclient -v dh10-eth0
dh60 dhclient -v dh60-eth0
dh100 dhclient -v dh100-eth0
dh10 ip addr show dh10-eth0
dh60 ip route
dhcphq cat tmp/dhcp_hq.leases
dh10 nslookup web.hq.local 10.1.0.10
```

Si se usa `pingall`, primero conviene correr `dhclient` en `dh10`, `dh60` y `dh100`, porque esos tres hosts arrancan sin IP a proposito para poder probar DHCP.

Resultado esperado para HTTP:

```html
<h1>MiniHub HQ Web Server</h1>
```
