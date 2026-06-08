#!/usr/bin/env bash
# Limpia cualquier estado previo de Mininet y arranca la topologia MiniHUB.
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[run] Limpiando estado previo de Mininet (mn -c)..."
sudo mn -c >/dev/null 2>&1 || true

# mn -c solo borra puertos registrados en OVS; las veth creadas con net.addLink()
# antes de net.start() quedan huerfanas en el kernel si el proceso murio a mitad del build.
echo "[run] Eliminando interfaces veth huerfanas..."
ip link show \
  | awk -F'[@: ]+' '/^[0-9]+:/ {print $2}' \
  | grep -E '^(shq|st[12]|swh|hhq|ht[12]|hwh|dhcp|rhq-|rt[12]-|rwh-|whr-)' \
  | xargs -r sudo ip link delete 2>/dev/null || true

echo "[run] Iniciando topologia MiniHUB..."
if [ -x "$DIR/.venv/bin/python" ]; then
    sudo "$DIR/.venv/bin/python" "$DIR/main.py"
else
    sudo python3 "$DIR/main.py"
fi
