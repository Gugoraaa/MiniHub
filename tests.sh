#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# MiniHUB - Guia de comandos de validacion.
#
# Este archivo NO se ejecuta directamente sobre Mininet: los comandos de prueba
# deben escribirse DENTRO de la CLI de Mininet (mininet> ...) que abre main.py.
# Aqui se documentan EXACTAMENTE los comandos a copiar/pegar y lo que se espera.
#
# Uso recomendado:   cat tests.sh   (leer)  ->  pegar los comandos en mininet>
# -----------------------------------------------------------------------------

cat <<'GUIA'

================ A. CONNECTIVITY TESTS (deben FUNCIONAR) =================
# Tienda1 checkout -> HQ Sales
h_t1_checkout ping -c 3 h_hq_sales
# Tienda2 checkout -> HQ Sales
h_t2_checkout ping -c 3 h_hq_sales
# Warehouse inventory -> HQ Inventory
h_wh_inventory ping -c 3 h_hq_inventory
# HQ IT -> Warehouse Admin
h_hq_it ping -c 3 h_wh_admin
# Tienda1 -> Warehouse por enlace WAN directo (10.0.4.0/30)
h_t1_checkout ping -c 3 h_wh_inventory
# Esperado: "3 packets transmitted, 3 received, 0% packet loss"

================ B. SECURITY VALIDATION (firewall) ======================
# 1) WiFi guest Tienda1 NO debe llegar a HQ            -> 100% loss
h_t1_wifi_guest ping -c 3 h_hq_sales
# 2) Sales NO debe acceder a impresoras                -> 100% loss
h_hq_sales ping -c 3 h_hq_printer
# 3) Customer Service NO debe acceder a Finance        -> 100% loss
h_hq_customer_service ping -c 3 h_hq_finance
# 4) Security Operations SI debe acceder a camaras     -> 0% loss
h_hq_security_ops ping -c 3 h_hq_camera
# 5) Un usuario comun (Sales) NO accede a camaras      -> 100% loss
h_hq_sales ping -c 3 h_hq_camera

# Evidencia de descarte con tcpdump (en otra terminal/xterm del router):
r_hq ip -br addr                 # listar interfaces e IPs del router
# Capturar ICMP entrante hacia camaras y ver que NO sale hacia la camara:
r_hq tcpdump -n -i any icmp
# (mientras corre, lanzar:  h_hq_sales ping -c 3 h_hq_camera  -> se ve la
#  solicitud llegar al router y NO ser reenviada por el DROP)

================ C. BANDWIDTH / QoS VALIDATION (iperf) ==================
# 1) Enlace HQ <-> Tienda1 = 20 Mbps
h_hq_sales iperf -s &
h_t1_checkout iperf -c 10.1.0.40 -t 10
# 2) Enlace HQ <-> Warehouse = 50 Mbps
h_hq_inventory iperf -s &
h_wh_inventory iperf -c 10.1.0.200 -t 10
# 3) Enlace Tienda1 <-> Warehouse = 15 Mbps (ruta directa 10.0.4.0/30)
h_wh_inventory iperf -s &
h_t1_checkout iperf -c 10.4.0.10 -t 10
# Esperado: throughput cercano (un poco por debajo) al limite del enlace.

# Util tambien:
# pingall                # matriz de conectividad completa
# links                  # estado de enlaces
# r_hq iptables -L FORWARD -n -v   # ver reglas y contadores de paquetes

GUIA
