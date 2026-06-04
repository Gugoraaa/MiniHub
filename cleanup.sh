#!/usr/bin/env bash
# Limpia Mininet y cualquier proceso/regla residual de la sesion MiniHUB.

echo "[cleanup] mn -c (limpia switches, hosts, veth, namespaces)..."
sudo mn -c >/dev/null 2>&1 || true

echo "[cleanup] Vaciando reglas iptables (filter) del host..."
sudo iptables -F 2>/dev/null || true
sudo iptables -t nat -F 2>/dev/null || true
sudo iptables -P FORWARD ACCEPT 2>/dev/null || true

echo "[cleanup] Matando procesos residuales (iperf, http.server, dnsmasq de prueba)..."
sudo pkill -f "iperf"        2>/dev/null || true
sudo pkill -f "http.server"  2>/dev/null || true
sudo pkill -f "pyftpdlib"    2>/dev/null || true

echo "[cleanup] Listo."
