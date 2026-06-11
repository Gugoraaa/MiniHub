# ============================================================
# MiniHUB - Topología Mininet
# Imagen reproducible para correr topology.py igual en todos lados
# ============================================================
# Ubuntu 24.04 trae Python 3.12 (coincide con .python-version)
FROM ubuntu:24.04

# Evita prompts interactivos durante apt
ENV DEBIAN_FRONTEND=noninteractive

# ------------------------------------------------------------
# Paquetes de sistema que necesita la topología:
#   mininet            -> framework + módulo python3 + Open vSwitch
#   openvswitch-switch -> demonios ovsdb-server / ovs-vswitchd (ovs-vsctl)
#   dnsmasq            -> servidores DHCP/DNS de las sedes
#   isc-dhcp-relay     -> dhcrelay (relay DHCP en los MLS)
#   isc-dhcp-client    -> dhclient (clientes DHCP de los hosts)
#   tcpdump            -> capturas / diagnóstico
#   curl               -> pruebas HTTP desde hosts Mininet
#   xterm              -> abrir terminales de hosts desde la CLI de Mininet
# ------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
        mininet \
        openvswitch-switch \
        openvswitch-common \
        dnsmasq \
        isc-dhcp-relay \
        isc-dhcp-client \
        tcpdump \
        curl \
        xterm \
        iproute2 \
        iputils-ping \
        net-tools \
        iperf \
        procps \
        ca-certificates \
        python3 \
    && rm -rf /var/lib/apt/lists/*

# El paquete dnsmasq deja un servicio que ocuparía el puerto 53 del
# namespace raíz; la topología lanza sus propios dnsmasq dentro de los
# hosts Mininet, así que apagamos el del sistema para evitar choques.
RUN systemctl disable dnsmasq 2>/dev/null || true

WORKDIR /app
COPY . /app

# Entrypoint: arranca Open vSwitch y limpia estado previo antes de
# ejecutar el comando (por defecto, topology.py).
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["python3", "topology.py"]
