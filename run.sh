#!/usr/bin/env bash
# Limpia cualquier estado previo de Mininet y arranca la topologia MiniHUB.
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[run] Limpiando estado previo de Mininet (mn -c)..."
sudo mn -c >/dev/null 2>&1 || true

echo "[run] Iniciando topologia MiniHUB..."
# Usa el Python del entorno uv si existe; si no, el python3 del sistema.
if [ -x "$DIR/.venv/bin/python" ]; then
    sudo "$DIR/.venv/bin/python" "$DIR/main.py"
else
    sudo python3 "$DIR/main.py"
fi
