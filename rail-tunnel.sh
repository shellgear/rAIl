#!/usr/bin/env bash
# SSH tunnel to a remote Hermes api_server (option [1] of setup.py).
# Reads RAIL_TUNNEL_TARGET / RAIL_TUNNEL_PORT from .env.
# Usage:  ./rail-tunnel.sh   (keep the terminal open, or add '&')
set -euo pipefail
cd "$(dirname "$0")"

if [ -f .env ]; then
    while IFS='=' read -r k v; do export "$k=$v"; done \
        < <(grep -E '^RAIL_TUNNEL_' .env || true)
fi

TARGET="${RAIL_TUNNEL_TARGET:-}"
PORT="${RAIL_TUNNEL_PORT:-8642}"

if [ -z "$TARGET" ]; then
    echo "RAIL_TUNNEL_TARGET non impostato: esegui prima 'python setup.py' (opzione [1])." >&2
    exit 1
fi

echo "Tunnel SSH: localhost:$PORT -> $TARGET:$PORT (Ctrl-C per chiudere)"
exec ssh -N \
    -o ExitOnForwardFailure=yes \
    -o ServerAliveInterval=30 \
    -p "${RAIL_TUNNEL_SSH_PORT:-22}" \
    -L "$PORT:localhost:$PORT" "$TARGET"
