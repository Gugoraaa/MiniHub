# Explicacion completa del HQ

Este documento explica la implementacion de HQ en `sites/hq.py` y los archivos secundarios que usa. La idea es que alguien pueda entender la topologia y los servicios aunque no este viendo el codigo al mismo tiempo.

## Objetivo de HQ

HQ representa una LAN corporativa con esta forma:

```text
hosts de usuario
    -> switches access s1, s2, s3, s4
    -> switch distribution s0
    -> switch capa 3 s5
    -> router WAN hqr
```

Ademas del camino principal, el switch L3 `s5` conecta tres servicios internos:

```text
s5 -> hdns    servidor DNS
s5 -> hweb    servidor HTTP
s5 -> dhcphq  servidor DHCP
```

Los hosts de usuario ya no tienen IP estatica. Arrancan con `ip=None` y obtienen direccion por DHCP usando `dhclient`.

## Archivos involucrados

- `sites/hq.py`: define la topologia, VLANs, switch L3, router WAN, DNS, HTTP y DHCP.
- `hq/site.conf`: configuracion del `dnsmasq` que funciona como DNS de HQ.
- `hq/records.txt`: registros DNS locales, por ejemplo `web.hq.local`.
- `hq/resolv.conf`: archivo que se monta en los hosts para que usen `10.1.0.10` como DNS.
- `tmp/dhcp_hq.conf`: pools DHCP por VLAN.
- `services/dhcp_server.py`: clase reutilizable que levanta `dnsmasq` como servidor DHCP.
- `master_wan.py`: runner que crea Mininet, construye HQ, configura servicios y abre CLI.
- `clean.sh`: limpieza previa de procesos y archivos temporales de HQ.

## Importaciones en `hq.py`

```python
import os

from router import Router
from services.dhcp_server import DHCPServer
from switchL3 import SwitchL3
```

`os` se usa para construir rutas absolutas hacia archivos de HQ, sobre todo para `resolv.conf`.

`Router` es la clase usada para crear `hqr`, el router de salida WAN.

`SwitchL3` es la clase del switch multilayer. Ese switch permite usar OVS como bridge y tambien tener interfaces internas con IP para rutear entre VLANs.

`DHCPServer` es la clase reutilizable del repo. Internamente crea un host Mininet y arranca `dnsmasq` con un archivo `.conf`.

## Constantes principales

En `HQSite`, las lineas 9 a 11 definen:

```python
VLANS = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120]
DHCPVLAN = 998
WANVLAN = 999
```

`VLANS` son las VLANs de usuario. Esas VLANs viajan por los trunks entre access, distribution y L3.

`DHCPVLAN = 998` es una VLAN de servicio. No es para usuarios. Sirve para conectar el switch L3 `s5` con el servidor DHCP `dhcphq`.

`WANVLAN = 999` es otra VLAN de servicio. Sirve para el enlace de transito entre `s5` y el router WAN `hqr`.

## Gateways/SVIs de usuario

`SVIGATEWAYS`, lineas 13 a 26, define la puerta de enlace de cada VLAN:

```python
10: '10.1.0.1/27'
20: '10.1.0.33/27'
...
120: '10.1.1.129/27'
```

Cada valor se convierte en una SVI dentro del switch L3 `s5`.

Una SVI es una interfaz virtual del switch para una VLAN. En un switch capa 3 real seria algo como:

```text
interface vlan 10
 ip address 10.1.0.1 255.255.255.224
```

En OVS/Mininet se logra creando un puerto interno con `type=internal`, asignandole un `tag` de VLAN y poniendole IP con comandos `ip`.

Gracias a estas SVIs, `s5` se vuelve gateway de todas las VLANs. Por ejemplo:

- VLAN 10 usa gateway `10.1.0.1`.
- VLAN 60 usa gateway `10.1.0.161`.
- VLAN 120 usa gateway `10.1.1.129`.

## Estado interno de la clase

En `__init__`, lineas 28 a 34:

```python
self.gateway = None
self.mls = None
self.hdns = None
self.hweb = None
self.dhcp = None
self.dnsclients = []
```

Estos atributos guardan referencias a nodos importantes:

- `gateway`: el router WAN `hqr`.
- `mls`: el switch capa 3 `s5`.
- `hdns`: el servidor DNS.
- `hweb`: el servidor HTTP.
- `dhcp`: el objeto `DHCPServer` de HQ.
- `dnsclients`: lista de hosts a los que se les monta `hq/resolv.conf`.

## Funcion `hqpath`

Lineas 36 a 39:

```python
def hqpath(self, filename):
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', 'hq', filename)
    )
```

Esta funcion devuelve la ruta absoluta hacia archivos dentro de la carpeta `MiniHub/hq`.

Se usa para montar `hq/resolv.conf` en los hosts. La ruta absoluta evita depender de desde que carpeta se haya ejecutado el script.

## Funcion `build`

`build(net)` crea nodos y enlaces. Todavia no configura VLANs ni IPs avanzadas. Esa parte ocurre despues en `configure()`, cuando Mininet ya hizo `net.start()`.

### Router WAN

Linea 43:

```python
self.gateway = net.addHost('hqr', cls=Router, ip=None)
```

Crea `hqr`, el router WAN de HQ. Se usa `ip=None` porque la IP se configura despues manualmente en `hqr-eth0`.

### Switches de la topologia

Lineas 46 a 55:

```python
hdist = net.addSwitch('s0', failMode='standalone')
hf1 = net.addSwitch('s1', failMode='standalone')
hf2 = net.addSwitch('s2', failMode='standalone')
hf3 = net.addSwitch('s3', failMode='standalone')
hf4 = net.addSwitch('s4', failMode='standalone')
self.mls = net.addSwitch('s5', cls=SwitchL3, failMode='standalone')
```

`s1` a `s4` son switches access, uno por piso.

`s0` es el switch de distribucion. Junta los cuatro access switches.

`s5` es el switch capa 3. Recibe el trunk desde `s0`, crea las SVIs y enruta entre VLANs.

`failMode='standalone'` permite que OVS haga forwarding sin depender de un controlador SDN externo.

### Hosts de usuario

Lineas 58 a 75:

```python
hit = net.addHost('hit', ip=None)
hsales = net.addHost('hsales', ip=None)
...
hphone = net.addHost('hphone', ip=None)
```

Estos son hosts representativos por area. Tienen `ip=None` porque ahora el objetivo es que reciban IP por DHCP.

Antes tenian IP estatica; con DHCP real, se prueban con:

```bash
hit dhclient -v hit-eth0
```

### Servidores internos

Lineas 78 a 89:

```python
self.hdns = net.addHost('hdns', ip=None)
self.hweb = net.addHost('hweb', ip=None)
self.dhcp = DHCPServer(...)
```

`hdns` sera el servidor DNS con IP `10.1.0.10/27`.

`hweb` sera el servidor HTTP con IP `10.1.0.11/27`.

`dhcphq` lo crea la clase `DHCPServer` con IP de servicio `192.168.101.10/24`.

Los parametros importantes de `DHCPServer` son:

- `name='dhcphq'`: nombre del host DHCP.
- `ip_cidr='192.168.101.10/24'`: IP del servidor.
- `gateway='192.168.101.254'`: gateway del servidor DHCP, que sera una SVI en `s5`.
- `conf_path='tmp/dhcp_hq.conf'`: archivo de pools.
- `pid_path`, `lease_path`, `log_path`: archivos temporales que usa `dnsmasq`.

### Lista `dnsclients`

Lineas 90 a 96:

```python
self.dnsclients = [
    hit, hsales, hsec,
    hmgmt, hhr, hfin,
    hinv, hcust, hpurch,
    hcam, hprint, hphone,
    self.hweb,
]
```

Esta lista contiene los hosts que deben usar el DNS de HQ. La funcion `mountresolv()` recorre esta lista y les monta `hq/resolv.conf`.

No se incluye `hdns` porque el mismo es el servidor DNS.

No se incluye `dhcphq` porque el servidor DHCP no necesita resolver nombres para cumplir su funcion.

### Enlaces de usuarios a access switches

Lineas 99 a 113 conectan hosts a sus switches access.

Ejemplo:

```python
net.addLink(hit, hf1, port2=1)
net.addLink(hsales, hf1, port2=2)
net.addLink(hsec, hf1, port2=3)
```

Esto significa:

- `hit` queda en `s1-eth1`.
- `hsales` queda en `s1-eth2`.
- `hsec` queda en `s1-eth3`.

Luego `configure()` etiqueta esos puertos con VLAN 10, 20 y 30.

### Enlaces access -> distribution

Lineas 116 a 119:

```python
net.addLink(hf1, hdist, port1=10, port2=1)
...
net.addLink(hf4, hdist, port1=10, port2=4)
```

Cada access switch usa su puerto 10 como uplink hacia `s0`.

Estos enlaces despues se configuran como trunks, porque deben transportar varias VLANs.

### Enlaces distribution -> L3 -> servicios

Lineas 122 a 126:

```python
net.addLink(hdist, self.mls, port1=24, port2=1)
net.addLink(self.mls, self.gateway, port1=2, intfName2='hqr-eth0')
net.addLink(self.mls, self.hdns, port1=3, intfName2='hdns-eth0')
net.addLink(self.mls, self.hweb, port1=4, intfName2='hweb-eth0')
net.addLink(self.mls, self.dhcp.host, port1=5, intfName2='dhcphq-eth0')
```

El mapa de puertos en `s5` queda asi:

- `s5-eth1`: trunk hacia `s0`.
- `s5-eth2`: enlace hacia router WAN `hqr`.
- `s5-eth3`: enlace hacia DNS `hdns`.
- `s5-eth4`: enlace hacia HTTP `hweb`.
- `s5-eth5`: enlace hacia DHCP `dhcphq`.

## Funcion `createsvi`

Lineas 135 a 145:

```python
def createsvi(self, vlanid, gatewaycidr, intfname=None):
    intfname = intfname or f'hqvlan{vlanid}'
```

Si no se pasa nombre, la interfaz se llama `hqvlan10`, `hqvlan20`, etc.

Luego:

```python
ovs-vsctl --may-exist add-port s5 hqvlan10 tag=10 -- set interface hqvlan10 type=internal
```

Esto crea un puerto interno en OVS, dentro del switch `s5`, asociado a la VLAN indicada.

Despues:

```python
ip addr flush dev hqvlan10
ip addr add 10.1.0.1/27 dev hqvlan10
ip link set hqvlan10 up
```

Se limpia cualquier IP anterior, se asigna la IP gateway de la VLAN y se levanta la interfaz.

Esta funcion es la base del routing inter-VLAN.

## DNS en HQ

### `configuredns`

Lineas 147 a 161:

```python
self.mls.cmd('ovs-vsctl set port s5-eth3 tag=10')
```

El puerto hacia `hdns` queda como access port en VLAN 10.

Luego:

```python
self.hdns.setIP('10.1.0.10/27', intf='hdns-eth0')
self.hdns.setDefaultRoute('via 10.1.0.1')
```

El servidor DNS vive en VLAN 10:

- IP: `10.1.0.10/27`
- Gateway: `10.1.0.1`

Despues se arranca `dnsmasq`:

```python
dnsmasq -d --conf-file=./hq/site.conf --pid-file=/tmp/dnsmasq-hq.pid &
```

`dnsmasq` lee `hq/site.conf`. El `&` lo deja corriendo en background.

### `hq/site.conf`

Contenido:

```conf
no-hosts
no-resolv
domain-needed
local=/hq.local/
log-queries
addn-hosts=./hq/records.txt
except-interface=lo
```

`no-hosts` evita que dnsmasq use `/etc/hosts`.

`no-resolv` evita que use resolvers externos del sistema. Esto hace que el DNS sea local.

`domain-needed` ayuda a rechazar consultas incompletas sin dominio.

`local=/hq.local/` declara `hq.local` como dominio local.

`log-queries` activa logs de consultas DNS.

`addn-hosts=./hq/records.txt` le dice a dnsmasq que lea registros desde `records.txt`.

`except-interface=lo` evita escuchar en loopback.

### `hq/records.txt`

Contenido actual:

```text
10.1.0.10 dns.hq.local dns.local
10.1.0.11 web.hq.local www.hq.local
10.1.0.1 gateway.it.hq.local
10.1.0.33 gateway.sales.hq.local
10.1.0.161 gateway.finance.hq.local
10.1.1.65 gateway.camera.hq.local
10.1.2.2 router.hq.local hqr.hq.local
```

Cada linea es:

```text
IP nombre1 nombre2
```

Por ejemplo:

```text
10.1.0.11 web.hq.local www.hq.local
```

Esto permite que un host haga:

```bash
curl http://web.hq.local
```

DNS convierte `web.hq.local` a `10.1.0.11`, y HTTP se conecta a esa IP.

### `mountresolv`

Lineas 163 a 169:

```python
source = self.hqpath('resolv.conf')
```

Busca la ruta absoluta de `hq/resolv.conf`.

Luego por cada host en `dnsclients`:

```python
host.cmd('umount /etc/resolv.conf 2>/dev/null || true')
host.cmd('touch /etc/resolv.conf')
host.cmd(f'mount --bind {source} /etc/resolv.conf')
```

Esto monta el archivo `hq/resolv.conf` encima de `/etc/resolv.conf` dentro del host.

El archivo `hq/resolv.conf` contiene:

```conf
nameserver 10.1.0.10
```

Resultado: esos hosts usan `hdns` como servidor DNS.

## HTTP en HQ

### `configurehttp`

Lineas 171 a 188:

```python
self.mls.cmd('ovs-vsctl set port s5-eth4 tag=10')
```

El puerto hacia `hweb` queda como access port en VLAN 10.

Luego:

```python
self.hweb.setIP('10.1.0.11/27', intf='hweb-eth0')
self.hweb.setDefaultRoute('via 10.1.0.1')
```

El servidor HTTP vive en VLAN 10:

- IP: `10.1.0.11/27`
- Gateway: `10.1.0.1`

Despues se crea el sitio:

```python
mkdir -p /tmp/hq-web
printf '<h1>MiniHub HQ Web Server</h1>' > /tmp/hq-web/index.html
```

Y se levanta el servidor:

```python
cd /tmp/hq-web && python3 -m http.server 80
```

El servidor escucha en puerto 80. Como `records.txt` tiene `web.hq.local -> 10.1.0.11`, los clientes pueden entrar con:

```bash
curl http://web.hq.local
```

Eso prueba DNS y HTTP juntos.

## DHCP en HQ

### Servidor `dhcphq`

En `build`, lineas 80 a 89, se crea:

```python
self.dhcp = DHCPServer(
    net=net,
    name='dhcphq',
    ip_cidr='192.168.101.10/24',
    gateway='192.168.101.254',
    conf_path='tmp/dhcp_hq.conf',
    pid_path='tmp/dhcp_hq.pid',
    lease_path='tmp/dhcp_hq.leases',
    log_path='tmp/dhcp_hq.log'
)
```

Este servidor no esta dentro de una VLAN de usuario. Esta en una VLAN de servicio:

- VLAN: `998`
- IP del servidor: `192.168.101.10/24`
- Gateway en `s5`: `192.168.101.254/24`

### `configuredhcp`

Lineas 190 a 216:

```python
self.mls.cmd(f'ovs-vsctl set port s5-eth5 tag={self.DHCPVLAN}')
self.createsvi(self.DHCPVLAN, '192.168.101.254/24', intfname='hqdhcp')
```

El puerto `s5-eth5` queda como access en VLAN 998.

La SVI `hqdhcp` es la puerta de enlace de la red de servicio DHCP.

Luego:

```python
self.dhcp.host.setIP('192.168.101.10/24', intf='dhcphq-eth0')
self.dhcp.host.cmd('ip route replace default via 192.168.101.254')
```

El host `dhcphq` recibe su IP estatica y su ruta default.

Despues:

```python
self.dhcp.start()
```

Eso llama a la clase `DHCPServer` de `services/dhcp_server.py`.

En esa clase, el metodo `start()` ejecuta:

```python
dnsmasq --conf-file=tmp/dhcp_hq.conf \
        --pid-file=tmp/dhcp_hq.pid \
        --dhcp-leasefile=tmp/dhcp_hq.leases \
        --log-dhcp \
        --log-facility=tmp/dhcp_hq.log
```

O sea, `dnsmasq` funciona como servidor DHCP y usa `tmp/dhcp_hq.conf`.

### DHCP relay

El servidor DHCP esta en VLAN 998, pero los clientes estan en VLANs 10, 20, 30, etc. Por eso se necesita relay.

Lineas 200 a 216:

```python
dhcrelay -4
    -i hqvlan10
    -i hqvlan20
    ...
    -i hqvlan120
    -i hqdhcp
    192.168.101.10
```

`dhcrelay` escucha solicitudes DHCP en las SVIs de usuario y las reenvia al servidor `192.168.101.10`.

Sin relay, el DHCP broadcast de una VLAN no llegaria al servidor porque el servidor esta en otra VLAN.

### `tmp/dhcp_hq.conf`

Este archivo define pools por VLAN.

Ejemplo de VLAN 10:

```conf
dhcp-range=set:vlan10,10.1.0.12,10.1.0.30,255.255.255.224,12h
dhcp-option=tag:vlan10,option:router,10.1.0.1
dhcp-option=tag:vlan10,option:dns-server,10.1.0.10
```

Esto dice:

- entregar IPs de `10.1.0.12` a `10.1.0.30`;
- usar mascara `/27`;
- lease de 12 horas;
- gateway `10.1.0.1`;
- DNS `10.1.0.10`.

En VLAN 10 el pool empieza en `.12` porque `.10` es DNS y `.11` es HTTP.

Las demas VLANs usan su propio rango, gateway y el mismo DNS `10.1.0.10`.

## Funcion `configure`

`configure()` se ejecuta despues de `net.start()`. Aqui se configura lo que necesita que las interfaces ya existan.

### Routing en `s5`

Lineas 222 a 226:

```python
sysctl -w net.ipv4.ip_forward=1
sysctl -w net.ipv4.conf.all.rp_filter=0
sysctl -w net.ipv4.conf.default.rp_filter=0
iptables -P FORWARD ACCEPT
iptables -F FORWARD
```

`ip_forward=1` permite que `s5` enrute paquetes entre interfaces.

`rp_filter=0` evita que Linux descarte trafico por filtros de ruta inversa, algo que puede molestar en topologias virtuales con varias VLANs.

`iptables -P FORWARD ACCEPT` y `iptables -F FORWARD` permiten forwarding sin reglas bloqueando.

### Puertos access

Lineas 229 a 250 configuran los puertos de usuarios.

Ejemplo:

```python
self.hf1.cmd('ovs-vsctl set port s1-eth1 tag=10')
self.hf1.cmd('ovs-vsctl set port s1-eth2 tag=20')
self.hf1.cmd('ovs-vsctl set port s1-eth3 tag=30')
```

`s1-eth1` queda en VLAN 10, `s1-eth2` en VLAN 20 y `s1-eth3` en VLAN 30.

El host no necesita saber nada de VLAN tags. El switch marca internamente el puerto.

### Trunks

Lineas 232, 238, 244 y 250 configuran trunks desde access switches hacia distribution.

Lineas 253 a 257 configuran trunks en `s0`.

Linea 260 configura el trunk entre `s0` y `s5`.

Un trunk transporta multiples VLANs por el mismo enlace. Aqui se usa:

```python
trunks={allowedvlans}
```

`allowedvlans` sale de:

```python
allowedvlans = ','.join(str(vlan) for vlan in self.VLANS)
```

Por eso el trunk permite VLANs 10 a 120.

### Creacion de SVIs

Lineas 263 y 264:

```python
for vlanid, gatewaycidr in self.SVIGATEWAYS.items():
    self.createsvi(vlanid, gatewaycidr)
```

Esto crea todas las interfaces `hqvlan10`, `hqvlan20`, etc.

Cada una recibe la IP gateway definida en `SVIGATEWAYS`.

### Enlace WAN

Lineas 268 a 273:

```python
self.mls.cmd(f'ovs-vsctl set port s5-eth2 tag={self.WANVLAN}')
self.createsvi(self.WANVLAN, '10.1.2.1/30', intfname='hqwan')
self.gateway.setIP('10.1.2.2/30', intf='hqr-eth0')
```

`s5-eth2` conecta a `hqr`.

La VLAN 999 tiene:

- `s5/hqwan`: `10.1.2.1/30`
- `hqr-eth0`: `10.1.2.2/30`

Eso crea una red punto a punto entre el switch L3 y el router WAN.

### Servicios

Lineas 276 a 278:

```python
self.configuredns()
self.configurehttp()
self.configuredhcp()
```

El orden es:

1. DNS: levanta `hdns` y monta resolv en clientes.
2. HTTP: levanta `hweb`.
3. DHCP: levanta `dhcphq` y `dhcrelay`.

### Rutas

Lineas 281 a 283:

```python
self.mls.cmd('ip route replace default via 10.1.2.2')
self.gateway.cmd('ip route replace 10.1.0.0/23 via 10.1.2.1')
self.gateway.cmd('ip route replace 192.168.101.0/24 via 10.1.2.1')
```

`s5` manda todo lo desconocido hacia el router WAN `10.1.2.2`.

`hqr` sabe regresar hacia:

- `10.1.0.0/23`: todas las VLANs de usuarios y servicios internos en HQ.
- `192.168.101.0/24`: red de servicio del DHCP.

## `master_wan.py`

`master_wan.py` es el runner.

Primero calcula:

```python
BASEDIR = os.path.dirname(os.path.abspath(__file__))
```

Luego `runclean()` ejecuta `clean.sh` antes de levantar la red.

En `buildmaster()`:

```python
os.chdir(BASEDIR)
runclean()
net = Mininet(...)
hq = HQSite()
hq.build(net)
net.start()
hq.configure()
CLI(net)
```

El orden importa:

1. Cambiar a carpeta `MiniHub`.
2. Limpiar procesos viejos.
3. Crear red Mininet.
4. Construir nodos/enlaces.
5. Iniciar red.
6. Configurar VLANs, SVIs, rutas y servicios.
7. Abrir CLI.
8. Al salir, hacer `net.stop()`.

## `clean.sh`

`clean.sh` limpia procesos y archivos temporales antes de una corrida nueva:

```bash
pkill -f 'dnsmasq.*hq/site.conf'
pkill -f 'dnsmasq.*tmp/dhcp_hq.conf'
pkill -f 'dhcrelay.*192.168.101.10'
pkill -f 'python3 -m http.server 80'
rm -f /tmp/dnsmasq-hq.pid /tmp/dnsmasq-hq.log
rm -f /tmp/http-hq.pid /tmp/http-hq.log
rm -f tmp/dhcp_hq.pid tmp/dhcp_hq.leases tmp/dhcp_hq.log
rm -rf /tmp/hq-web
mn -c
```

Esto evita que una corrida anterior deje procesos o interfaces que rompan la siguiente.

## Como probar HQ

Arrancar:

```bash
sudo python3 master_wan.py
```

Dentro de Mininet, primero pedir DHCP:

```bash
hit dhclient -v hit-eth0
hsales dhclient -v hsales-eth0
hfin dhclient -v hfin-eth0
hcam dhclient -v hcam-eth0
```

Verificar lease:

```bash
hit ip addr show hit-eth0
hit ip route
hit cat /etc/resolv.conf
```

Probar gateway:

```bash
hit ping -c 3 10.1.0.1
```

Probar inter-VLAN:

```bash
hfin ping -c 3 10.1.0.1
```

Probar WAN transit:

```bash
s5 ping -c 3 10.1.2.2
hqr ping -c 3 10.1.2.1
hit ping -c 3 10.1.2.2
```

Probar DNS:

```bash
hit nslookup dns.hq.local
hit nslookup web.hq.local
```

Probar HTTP usando DNS:

```bash
hit curl http://web.hq.local
```

Si ese comando devuelve:

```html
<h1>MiniHub HQ Web Server</h1>
```

entonces DNS y HTTP estan trabajando juntos correctamente.

## Nota sobre `pingall`

Con DHCP, `pingall` puede no ser una buena prueba.

La razon es que los hosts arrancan con `ip=None` y Mininet no siempre actualiza su cache interna de IP despues de `dhclient`. Entonces `pingall` puede intentar hacer ping a `None` aunque el host ya tenga IP real dentro de Linux.

Para DHCP es mejor probar con:

```bash
host dhclient -v host-eth0
host ip addr show host-eth0
host ping -c 3 gateway
```

## Resumen mental rapido

`s5` es el corazon de HQ.

Hace cuatro trabajos:

1. Recibe VLANs desde `s0` por trunk.
2. Crea SVIs para ser gateway de cada VLAN.
3. Enruta hacia `hqr` por la VLAN 999.
4. Conecta servicios locales: DNS, HTTP y DHCP.

DNS da nombres.

HTTP da una pagina.

DHCP da IPs.

`dhcrelay` conecta los clientes DHCP de todas las VLANs con el servidor DHCP central `dhcphq`.
