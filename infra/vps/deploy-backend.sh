#!/usr/bin/env bash
# Actualiza el backend en el VPS con lo último de GitHub. Como root:
#   bash /opt/barrio/repo/infra/vps/deploy-backend.sh
# Las migraciones de la base se aplican solas al arrancar el servicio.
set -euo pipefail

REPO_DIR="/opt/barrio/repo"
NODE_BIN="/opt/barrio/node/bin"
PORT="$(grep '^PORT=' /etc/barrio/backend.env | cut -d= -f2)"

sudo -u barrio git -C "$REPO_DIR" pull --ff-only
sudo -u barrio env PATH="$NODE_BIN:$PATH" bash -c "cd '$REPO_DIR/backend' && npm ci && npm run build"
systemctl restart barrio-backend

for attempt in $(seq 1 15); do
  if curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null; then
    echo "Backend actualizado: $(git -C "$REPO_DIR" log --oneline -1)"
    exit 0
  fi
  sleep 1
done

echo "El backend no respondió. Ver: journalctl -u barrio-backend -n 50" >&2
exit 1
