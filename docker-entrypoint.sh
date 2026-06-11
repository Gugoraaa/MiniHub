#!/usr/bin/env bash
# ============================================================
# Entrypoint del contenedor MiniHUB.
# Arranca Open vSwitch (que NO usa systemd dentro del contenedor)
# y limpia estado previo de Mininet antes de lanzar la topología.
# ============================================================
set -e

echo "[entrypoint] Iniciando Open vSwitch..."
mkdir -p /var/run/openvswitch
# ovs-ctl crea la base de datos si no existe y levanta
# ovsdb-server + ovs-vswitchd sin necesidad de systemd.
/usr/share/openvswitch/scripts/ovs-ctl --system-id=random start

echo "[entrypoint] Limpiando estado previo de Mininet..."
mn -c >/dev/null 2>&1 || true

echo "[entrypoint] Listo. Ejecutando: $*"
exec "$@"
