# topologiaMiniHub

Implementación en **Mininet** de la red empresarial **MiniHUB** (HQ / Sede Central,
Tienda Retail #1, Tienda Retail #2 y Warehouse / Almacén), usando Python y `uv`.

Versión **abstracta, funcional y validable** de la topología completa: cada VLAN se
representa con un host representativo (Principio de Abstracción) y se prueba que el
diseño lógico funciona — routing entre sedes, segmentación L3, firewall, enlaces WAN
con límite de ancho de banda, y validación automática con `ping`, `iperf` y `tcpdump`.

Sigue la metodología vista en clase (`documentacion/s7exe.pdf`): clase `Router(Node)`
personalizada, `Mininet(controller=None, switch=OVSSwitch, link=TCLink)`, switches
OVS en modo `standalone`, routers Linux con rutas estáticas, TCLink para QoS WAN y
firewall con `iptables` aplicado vía `router.cmd()`.

---

## 1. Dependencias del sistema

Mininet requiere binarios del sistema (no basta el paquete pip). Instala todo de
una vez con:

```bash
sudo apt-get update
sudo apt-get install -y \
  mininet \
  openvswitch-switch \
  iptables \
  dnsmasq \
  iperf \
  tcpdump \
  net-tools \
  iputils-ping
```

> **`iptables` es obligatorio.** Sin él el firewall no aplica ninguna regla, los
> flujos que deberían estar bloqueados pasan libremente y los tests de seguridad
> marcan `FAIL` (verás `0% loss` donde debería haber `100% loss`).

> **`iperf` (v2)** es el que usa `iperf -s` / `iperf -c`. En algunos sistemas el
> paquete se llama `iperf` (v2) y en otros `iperf3`; la topología usa la sintaxis
> de v2. Instala `iperf` (no `iperf3`).

### Verificar antes de ejecutar

```bash
# Todos deben devolver una ruta, no "command not found"
command -v mnexec       # /usr/bin/mnexec
command -v ovs-vsctl    # /usr/bin/ovs-vsctl
command -v iptables     # /usr/sbin/iptables  (o /usr/bin/iptables)
command -v dnsmasq      # /usr/sbin/dnsmasq   (DHCP)
command -v iperf        # /usr/bin/iperf
command -v tcpdump      # /usr/bin/tcpdump
```

En **WSL2** el servicio de Open vSwitch debe estar activo:

```bash
sudo service openvswitch-switch start
# Verificar:
sudo service openvswitch-switch status
```

---

## 2. Instalar dependencias Python (uv)

```bash
# Instalar uv si no lo tienes
curl -LsSf https://astral.sh/uv/install.sh | sh

# Crear .venv e instalar paquetes del proyecto
uv sync
```

---

## 3. Cómo ejecutar

La aplicación es **`main.py`** en la raíz. Siempre requiere `sudo` porque Mininet
crea namespaces de red y veth pairs.

### Ejecución recomendada (tests automáticos + CLI)

```bash
bash run.sh
```

`run.sh` hace `mn -c` (limpia estado anterior) y luego lanza `main.py`. Al
arrancar la topología:

1. Crea 4 routers, 14 switches, 34 hosts representativos + `dhcp_hq`.
2. Configura IPs, rutas estáticas y reglas iptables.
3. Corre automáticamente los **13 tests** (conectividad, firewall, ancho de banda)
   e imprime `PASS`/`FAIL` en color.
4. Abre la **CLI interactiva de Mininet** (`mininet>`).

Equivalente directo sin el script:

```bash
sudo .venv/bin/python main.py
```

### Ejecutar sin tests (solo CLI)

Para ir directo a la CLI sin esperar los tests automáticos:

```bash
sudo .venv/bin/python main.py --skip-tests
```

### Ejecutar con diagnóstico

Si algún test falla, este flag imprime las IPs, tablas de rutas y reglas `FORWARD`
de cada router justo antes de los tests, para identificar el problema:

```bash
sudo .venv/bin/python main.py --diag
```

### Limpiar estado de Mininet

Si la topología se cierra mal y quedan procesos/interfaces/switches colgados:

```bash
bash cleanup.sh
```

Hace `mn -c`, vacía las cadenas de iptables del host y mata procesos residuales
(`iperf`, `http.server`, etc.).

### Tabla de flags

| Flag | Efecto |
|------|--------|
| *(ninguno)* | Tests automáticos + CLI |
| `--skip-tests` | Salta los tests, abre solo la CLI |
| `--diag` | Imprime IPs/rutas/iptables de routers antes de los tests |
| `--skip-tests --diag` | Diagnóstico sin tests, luego CLI |

---

## 4. Scripts incluidos

| Archivo | Descripción |
|---------|-------------|
| `main.py` | Topología completa. Punto de entrada principal. |
| `run.sh` | Limpia Mininet (`mn -c`) y lanza `main.py`. Detecta `.venv/bin/python` automáticamente. |
| `cleanup.sh` | `mn -c` + vaciar iptables + matar procesos residuales (iperf, http.server). |
| `tests.sh` | Referencia de todos los comandos de prueba con explicación. Leer y copiar en `mininet>`. |
| `firewall_rules.sh` | Las reglas iptables exactas que aplica `main.py`, en formato de referencia. |

---

## 5. Tests automáticos

Al arrancar con `bash run.sh` (o `sudo .venv/bin/python main.py`) se corren 13
tests agrupados en tres secciones:

### A — Connectivity Tests (5 tests, deben dar PASS)

Verifican que el routing inter-sede funciona end-to-end.

| Test | Src | Dst | Enlace usado |
|------|-----|-----|--------------|
| T1 checkout → HQ sales | `h_t1_checkout` | `h_hq_sales` | WAN 10.0.1.0/30 (20 Mbps) |
| T2 checkout → HQ sales | `h_t2_checkout` | `h_hq_sales` | WAN 10.0.2.0/30 (20 Mbps) |
| WH inventory → HQ inventory | `h_wh_inventory` | `h_hq_inventory` | WAN 10.0.3.0/30 (50 Mbps) |
| HQ IT → WH admin | `h_hq_it` | `h_wh_admin` | WAN 10.0.3.0/30 |
| T1 checkout → WH inventory | `h_t1_checkout` | `h_wh_inventory` | WAN directo 10.0.4.0/30 (15 Mbps) |

### B — Security Tests (5 tests, resultado esperado según política)

| Test | Src | Dst | Esperado | Política |
|------|-----|-----|----------|----------|
| WiFi guest T1 → HQ sales | `h_t1_wifi_guest` | `h_hq_sales` | BLOQUEADO | P3 guest WiFi |
| HQ sales → HQ printer | `h_hq_sales` | `h_hq_printer` | BLOQUEADO | P1 impresoras |
| HQ customer service → HQ finance | `h_hq_customer_service` | `h_hq_finance` | BLOQUEADO | P4 finance |
| HQ security ops → HQ camera | `h_hq_security_ops` | `h_hq_camera` | FUNCIONA | P2 SecOps→cámaras |
| HQ sales → HQ camera | `h_hq_sales` | `h_hq_camera` | BLOQUEADO | P2 cámaras |

### C — Bandwidth Tests (3 tests, deben dar PASS)

Verifican que TCLink limita el throughput al valor configurado.

| Test | Servidor | Cliente | Límite esperado |
|------|----------|---------|-----------------|
| HQ ↔ T1 | `h_hq_sales` | `h_t1_checkout` | ≤ 20 Mbps |
| HQ ↔ Warehouse | `h_hq_inventory` | `h_wh_inventory` | ≤ 50 Mbps |
| T1 ↔ WH directo | `h_wh_inventory` | `h_t1_checkout` | ≤ 15 Mbps |

---

## 6. Pruebas manuales en la CLI

Después de los tests automáticos queda abierta la CLI (`mininet>`). Comandos útiles:

```text
# Ver estado general
nodes                              # lista todos los nodos
links                              # estado de los enlaces
dump                               # IPs y PIDs de todos los hosts

# Conectividad manual
h_t1_checkout ping -c 3 h_hq_sales
h_wh_inventory ping -c 3 h_hq_inventory

# Firewall: evidencia de descarte
r_hq ip -br addr                   # IPs de cada interfaz del router HQ
r_hq iptables -L FORWARD -n -v    # reglas + contadores de paquetes
r_hq tcpdump -n -i any icmp       # capturar ICMP en tiempo real

# iperf manual
h_hq_sales iperf -s &
h_t1_checkout iperf -c 10.1.0.40 -t 10    # ~20 Mbps

# Simular caída de enlace
link r_t1 r_wh down                # cortar enlace directo T1-WH
link r_t1 r_wh up                  # restaurar
```

Lista completa con salidas esperadas en `results/comandos_validacion.md`.

---

## 7. Diseño de la topología

### Principio de Abstracción

La topología Draw.io tiene decenas de dispositivos por sede. En Mininet se usa
**un host representativo por VLAN**. La segmentación es real (subredes VLSM
distintas) y el firewall la hace cumplir en L3.

### Modelo L2 por sede

```
hosts → switch de piso (s_*_floorN) → switch core (s_*_core) → router (r_*)
```

El router tiene **una interfaz por VLAN** cuya IP es el gateway de esa VLAN.
Como cada host solo conoce su `/27` (u otro prefijo) y su default route, todo
el tráfico inter-VLAN pasa obligatoriamente por el router, donde `iptables`
aplica las políticas aunque el plano L2 sea compartido.

El router usa `arp_ignore=1` / `arp_announce=2` y `rp_filter=0` por interfaz
para evitar problemas de ARP flux en el plano compartido.

### Direccionamiento VLSM oficial

| Sede | Bloque | Ejemplo de VLAN |
|------|--------|-----------------|
| HQ | 10.1.0.0/23 | IT: 10.1.0.0/27, Sales: 10.1.0.32/27 |
| Tienda #1 | 10.2.0.0/23 | Guest WiFi: 10.2.0.0/24, Checkout: 10.2.1.0/27 |
| Tienda #2 | 10.3.0.0/23 | (misma estructura que T1) |
| Warehouse | 10.4.0.0/23 | Inventory: 10.4.0.0/27, Shipping: 10.4.0.96/28 |
| WAN | 10.0.0.0/24 | en subredes /30 por enlace |

### WAN (TCLink con QoS)

| Enlace | Subred | Ancho de banda | Latencia |
|--------|--------|----------------|----------|
| HQ ↔ Tienda #1 | 10.0.1.0/30 | 20 Mbps | 10 ms |
| HQ ↔ Tienda #2 | 10.0.2.0/30 | 20 Mbps | 10 ms |
| HQ ↔ Warehouse | 10.0.3.0/30 | 50 Mbps | 8 ms |
| Tienda #1 ↔ Warehouse | 10.0.4.0/30 | 15 Mbps | 12 ms |
| Tienda #2 ↔ Warehouse | 10.0.5.0/30 | 15 Mbps | 12 ms |

### Routing estático

- Los routers de sede (T1, T2, WH) tienen `default via HQ`.
- T1 y T2 tienen ruta directa a WH (`10.4.0.0/23`) por el enlace `/30` dedicado.
- WH tiene rutas directas a T1 y T2 por sus respectivos enlaces directos.
- HQ tiene rutas explícitas a T1, T2 y WH.

### Tabla de nodos representativos (selección)

| Nodo | IP | VLAN | Sede |
|------|----|------|------|
| h_hq_it | 10.1.0.10/27 | VLAN 10 | HQ |
| h_hq_sales | 10.1.0.40/27 | VLAN 20 | HQ |
| h_hq_security_ops | 10.1.0.70/27 | VLAN 30 | HQ |
| h_hq_finance | 10.1.0.170/27 | VLAN 60 | HQ |
| h_hq_camera | 10.1.1.70/27 | VLAN 100 | HQ |
| h_hq_printer | 10.1.1.100/27 | VLAN 110 | HQ |
| h_t1_wifi_guest | 10.2.0.10/24 | VLAN 130 | Tienda #1 |
| h_t1_checkout | 10.2.1.10/27 | VLAN 140 | Tienda #1 |
| h_wh_inventory | 10.4.0.10/27 | VLAN 70 | Warehouse |
| dhcp_hq | 10.1.0.11/27 | — | HQ (nodo DHCP representativo) |

Tabla completa (34 hosts) en `results/chapter5_mininet_validation.md` §5.1.

### DHCP

Al arrancar, `main.py` inicia un servidor **`dnsmasq`** dentro del namespace de
cada router. Cada servidor sirve DHCP para todas las VLANs de su sede.

| Router | VLANs servidas | Pool de ejemplo |
|--------|---------------|-----------------|
| r_hq | 12 VLANs | VLAN 20 Sales: 10.1.0.49–10.1.0.62 |
| r_t1 | 6 VLANs | VLAN 130 Guest WiFi: 10.2.0.129–10.2.0.254 |
| r_t2 | 6 VLANs | VLAN 130 Guest WiFi: 10.3.0.129–10.3.0.254 |
| r_wh | 7 VLANs | VLAN 70 Inventory: 10.4.0.17–10.4.0.30 |

Los **hosts representativos** conservan su IP estática (que queda fuera del pool
DHCP — en la mitad inferior de la subred). Los pools usan la mitad superior.
Las subredes /30 (teléfonos) no tienen pool porque solo tienen 2 IPs útiles.

Para demostrar DHCP desde la CLI de Mininet:

```text
h_hq_sales ip addr flush dev h_hq_sales-eth0   # quitar IP estática
h_hq_sales dhclient -v h_hq_sales-eth0          # solicitar IP por DHCP
h_hq_sales ip addr                              # verificar IP asignada
```

Requiere que `dnsmasq` esté instalado:

```bash
sudo apt-get install -y dnsmasq
```

Si `dnsmasq` no está instalado la topología igual funciona (el DHCP se omite
y los hosts conservan sus IPs estáticas). El nodo `dhcp_hq` representa el
servicio de DHCP centralizado del diseño original.

---

## 8. Políticas de firewall

Aplicadas en la cadena `FORWARD` de cada router. Política por defecto: `ACCEPT`.
Las reglas `ACCEPT` específicas van **antes** de los `DROP` generales.

| # | Política | Origen bloqueado | Destino | Router |
|---|----------|-----------------|---------|--------|
| P1 | Impresoras aisladas | Sales, HR, Customer Service | `10.1.1.96/27` | r_hq |
| P2 | Cámaras aisladas | Todos excepto SecOps | `10.1.1.64/27` | r_hq |
| P2 | SecOps → cámaras | — | `10.1.1.64/27` | r_hq (ACCEPT explícito) |
| P3 | WiFi guest aislado | `10.2.0.0/24`, `10.3.0.0/24` | Redes internas | r_t1, r_t2 |
| P4 | Finance restringido | Todos excepto IT y Management | `10.1.0.160/27` | r_hq |
| P5 | Operación necesaria | — | — | (flujos permitidos por defecto) |

Reglas exactas en `firewall_rules.sh` y en `results/chapter5_mininet_validation.md` §5.2.

---

## 9. Solución de problemas (Troubleshooting)

### `Unable to derive default datapath ID`

OVS no puede derivar el DPID de nombres descriptivos como `s_hq_core`. Ya está
resuelto en el código (`dpid` explícito en cada `addSwitch`), pero si aparece
al modificar la topología asegúrate de pasar `dpid=_dpid()`.

### `sch_htb: quantum of class 50001 is big`

Advertencia **no fatal** del scheduler HTB del kernel de Linux. Aparece cuando el
ancho de banda de un TCLink produce un quantum grande. No afecta el funcionamiento
de los límites de bw ni de la latencia. Se puede ignorar.

### Tests de conectividad dan 100% loss (cross-site)

Causas más comunes:

1. **IPs WAN no asignadas.** `main.py` las asigna explícitamente tras `net.start()`.
   Si modificas la topología, verifica con `--diag` que cada interfaz WAN tiene IP.
2. **Rutas estáticas fallaron.** Con `--diag` o desde la CLI: `r_hq ip route`.
3. **rp_filter activo.** Resuelto con el bucle `for f in .../rp_filter; do echo 0 > $f`.

### Tests de seguridad dan 0% loss (nada se bloquea)

`iptables` no está instalado o no funciona. Verifica:

```bash
command -v iptables          # debe devolver una ruta
sudo iptables -L FORWARD -n  # debe mostrar la cadena FORWARD
```

Si no está instalado:

```bash
sudo apt-get install -y iptables
```

En sistemas modernos (Ubuntu 22.04+) puede ser necesario seleccionar la versión
legacy:

```bash
sudo update-alternatives --set iptables /usr/sbin/iptables-legacy
sudo update-alternatives --set ip6tables /usr/sbin/ip6tables-legacy
```

### `mnexec: command not found`

El paquete pip `mininet` no incluye `mnexec`. Instala Mininet del sistema:

```bash
sudo apt-get install -y mininet
```

### OVS switches no inician / `ovs-vsctl: command not found`

```bash
sudo apt-get install -y openvswitch-switch
sudo service openvswitch-switch start
```

### Procesos colgados tras un crash

```bash
bash cleanup.sh
```

---

## 10. Documentación del reporte

| Archivo | Contenido |
|---------|-----------|
| `results/chapter5_mininet_validation.md` | **Chapter 5** completo (§5.1 Abstracción, §5.2 Firewall, §5.3 Validación empírica) listo para pegar en el reporte |
| `results/comandos_validacion.md` | Comandos exactos y salidas esperadas para todas las pruebas |
| `firewall_rules.sh` | Reglas iptables de referencia con comentarios |
| `tests.sh` | Guía de pruebas manuales con explicación de cada comando |



### 11. Correr pruebas 
``` python
py exec(open("validate_network.py").read()); run_validation(net)
```