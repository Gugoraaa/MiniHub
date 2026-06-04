#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# MiniHUB - Reglas de firewall (iptables) - REFERENCIA
#
# Estas son EXACTAMENTE las reglas que main.py aplica automaticamente dentro
# del namespace de cada router via router.cmd('iptables ...'). Se incluyen aqui
# como referencia y para poder re-aplicarlas manualmente desde la CLI de Mininet:
#
#     mininet> r_hq sh -c 'iptables -A FORWARD ...'
#
# Regla de oro: las reglas ACCEPT especificas van ANTES de los DROP generales.
# Politica por defecto de la cadena FORWARD: ACCEPT.
# Habilitar reenvio:  sysctl -w net.ipv4.ip_forward=1   (lo hace la clase Router)
# -----------------------------------------------------------------------------

cat <<'RULES'

############################  r_hq  ############################
# Subredes sensibles HQ
#   Impresoras  10.1.1.96/27   Camaras 10.1.1.64/27   Finance 10.1.0.160/27
#   IT 10.1.0.0/27   Management 10.1.0.96/27   SecOps 10.1.0.64/27
#   Sales 10.1.0.32/27   HR 10.1.0.128/27   CustomerSvc 10.1.1.0/27

iptables -P FORWARD ACCEPT

# Politica 2 - Camaras: permitir Security Operations primero
iptables -A FORWARD -s 10.1.0.64/27 -d 10.1.1.64/27 -j ACCEPT

# Politica 4 - Finance: permitir IT y Management primero
iptables -A FORWARD -s 10.1.0.0/27  -d 10.1.0.160/27 -j ACCEPT
iptables -A FORWARD -s 10.1.0.96/27 -d 10.1.0.160/27 -j ACCEPT

# Politica 1 - Impresoras: usuarios comunes bloqueados
iptables -A FORWARD -s 10.1.0.32/27  -d 10.1.1.96/27 -j DROP   # Sales
iptables -A FORWARD -s 10.1.0.128/27 -d 10.1.1.96/27 -j DROP   # HR
iptables -A FORWARD -s 10.1.1.0/27   -d 10.1.1.96/27 -j DROP   # Customer Service

# Politica 2 - Camaras: bloquear a todos los demas
iptables -A FORWARD -d 10.1.1.64/27 -j DROP

# Politica 4 - Finance: bloquear a todos los demas
iptables -A FORWARD -d 10.1.0.160/27 -j DROP

############################  r_t1  ############################
# Politica 3 - WiFi Invitados (10.2.0.0/24) sin acceso a redes internas
iptables -P FORWARD ACCEPT
iptables -A FORWARD -s 10.2.0.0/24 -d 10.1.0.0/23 -j DROP
iptables -A FORWARD -s 10.2.0.0/24 -d 10.2.1.0/24 -j DROP
iptables -A FORWARD -s 10.2.0.0/24 -d 10.3.1.0/24 -j DROP
iptables -A FORWARD -s 10.2.0.0/24 -d 10.4.0.0/23 -j DROP
# Aislamiento local de impresoras/camaras de la tienda
iptables -A FORWARD -s 10.2.1.0/27 -d 10.2.1.80/29 -j DROP
iptables -A FORWARD -s 10.2.1.0/27 -d 10.2.1.64/28 -j DROP

############################  r_t2  ############################
iptables -P FORWARD ACCEPT
iptables -A FORWARD -s 10.3.0.0/24 -d 10.1.0.0/23 -j DROP
iptables -A FORWARD -s 10.3.0.0/24 -d 10.2.1.0/24 -j DROP
iptables -A FORWARD -s 10.3.0.0/24 -d 10.3.1.0/24 -j DROP
iptables -A FORWARD -s 10.3.0.0/24 -d 10.4.0.0/23 -j DROP
iptables -A FORWARD -s 10.3.1.0/27 -d 10.3.1.80/29 -j DROP
iptables -A FORWARD -s 10.3.1.0/27 -d 10.3.1.64/28 -j DROP

############################  r_wh  ############################
iptables -P FORWARD ACCEPT
iptables -A FORWARD -s 10.4.0.32/27 -d 10.4.0.144/29 -j DROP   # admin -> impresoras
iptables -A FORWARD -s 10.4.0.96/28 -d 10.4.0.128/28 -j DROP   # shipping -> camaras

RULES
