#!/usr/bin/env bash
# clean_mininet.sh
# Limpieza completa para topologías Mininet + OVS + DHCP
# Uso:
#   chmod +x clean_mininet.sh
#   sudo ./clean_mininet.sh

set -e

RED="\033[0;31m"
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
CYAN="\033[0;36m"
RESET="\033[0m"

echo -e "${CYAN}=========================================${RESET}"
echo -e "${CYAN} Limpieza completa de Mininet / DHCP / OVS ${RESET}"
echo -e "${CYAN}=========================================${RESET}"

if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}[ERROR] Ejecuta este script con sudo:${RESET}"
  echo "sudo ./clean_mininet.sh"
  exit 1
fi

echo -e "${YELLOW}[1/8] Matando clientes DHCP en hosts Mininet...${RESET}"
pkill -f "dhclient" 2>/dev/null || true

echo -e "${YELLOW}[2/8] Matando DHCP relays...${RESET}"
pkill -f "dhcrelay" 2>/dev/null || true

echo -e "${YELLOW}[3/8] Matando dnsmasq de las topologías...${RESET}"
pkill -f "dhcp_warehouse" 2>/dev/null || true
pkill -f "dhcp_tienda2" 2>/dev/null || true
pkill -f "dhcp_tienda1" 2>/dev/null || true
pkill -f "dhcp_campus" 2>/dev/null || true

echo -e "${YELLOW}[4/8] Limpiando Mininet...${RESET}"
mn -c 2>/dev/null || true

echo -e "${YELLOW}[5/8] Eliminando bridges OVS huérfanos de Mininet...${RESET}"
if command -v ovs-vsctl >/dev/null 2>&1; then
  for br in $(ovs-vsctl list-br 2>/dev/null | grep -E '^s[0-9]+$' || true); do
    echo "  Eliminando bridge OVS: $br"
    ovs-vsctl --if-exists del-br "$br" 2>/dev/null || true
  done

  for br in wh_mls wh_s1 wh_s2 wh_dist hq_mls hq_dist t2_mls t2_s1 t2_s2; do
    ovs-vsctl --if-exists del-br "$br" 2>/dev/null || true
  done
else
  echo -e "${YELLOW}[WARN] ovs-vsctl no está instalado o no está en PATH.${RESET}"
fi

echo -e "${YELLOW}[6/8] Eliminando interfaces internas/SVIs huérfanas...${RESET}"
for intf in $(ip -o link show | awk -F': ' '{print $2}' | grep -E '^(vlan[0-9]+|wh_vlan[0-9]+|t2_vlan[0-9]+|hq_vlan[0-9]+|hqwan)$' || true); do
  echo "  Eliminando interfaz: $intf"
  ip link delete "$intf" 2>/dev/null || true
done

echo -e "${YELLOW}[7/8] Borrando archivos temporales DHCP...${RESET}"
rm -f tmp/dhcp_warehouse.pid tmp/dhcp_warehouse.leases tmp/dhcp_warehouse.log 2>/dev/null || true
rm -f tmp/dhcp_tienda2.pid tmp/dhcp_tienda2.leases tmp/dhcp_tienda2.log 2>/dev/null || true
rm -f tmp/dhcp_tienda1.pid tmp/dhcp_tienda1.leases tmp/dhcp_tienda1.log 2>/dev/null || true

rm -f /tmp/dhcp_warehouse.pid /tmp/dhcp_warehouse.leases /tmp/dhcp_warehouse.log 2>/dev/null || true
rm -f /tmp/dhcp_tienda2.pid /tmp/dhcp_tienda2.leases /tmp/dhcp_tienda2.log 2>/dev/null || true
rm -f /tmp/dhcp_tienda1.pid /tmp/dhcp_tienda1.leases /tmp/dhcp_tienda1.log 2>/dev/null || true

echo -e "${YELLOW}[8/8] Estado final de procesos relevantes...${RESET}"
echo "Procesos dhclient/dhcrelay/dnsmasq restantes:"
ps aux | grep -E "dhclient|dhcrelay|dnsmasq" | grep -v grep || echo "  Ninguno"

echo
echo "Bridges OVS restantes tipo Mininet:"
if command -v ovs-vsctl >/dev/null 2>&1; then
  ovs-vsctl list-br 2>/dev/null | grep -E '^s[0-9]+$' || echo "  Ninguno"
else
  echo "  ovs-vsctl no disponible"
fi

echo -e "${GREEN}=========================================${RESET}"
echo -e "${GREEN} Limpieza terminada correctamente.${RESET}"
echo -e "${GREEN} Ahora puedes correr: uv run main.py${RESET}"
echo -e "${GREEN}=========================================${RESET}"
