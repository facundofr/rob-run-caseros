#!/usr/bin/env bash
# Prepara el VPS (Ubuntu 22.04 o 24.04) para Barrio: backend, PostgreSQL, HTTPS y servidor de juego.
# Uso, como root en el VPS:
#   git clone https://github.com/facundofr/rob-run-caseros.git /opt/barrio/repo
#   bash /opt/barrio/repo/infra/vps/setup-vps.sh
# Se puede volver a ejecutar: no pisa secretos ni bases existentes.
set -euo pipefail

API_DOMAIN="${API_DOMAIN:-api.facundofr.com}"
REPO_DIR="/opt/barrio/repo"
ENV_FILE="/etc/barrio/backend.env"

if [[ $EUID -ne 0 ]]; then
  echo "Ejecutar como root." >&2
  exit 1
fi

echo "==> Paquetes base"
apt-get update
apt-get install -y curl ca-certificates gnupg ufw git openssl postgresql debian-keyring debian-archive-keyring apt-transport-https

echo "==> Node.js 24"
if ! command -v node >/dev/null || [[ "$(node -v)" != v24* ]]; then
  curl -fsSL https://deb.nodesource.com/setup_24.x | bash -
  apt-get install -y nodejs
fi

echo "==> Caddy (HTTPS automático con Let's Encrypt)"
if ! command -v caddy >/dev/null; then
  curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/gpg.key | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update
  apt-get install -y caddy
fi

echo "==> Usuario y carpetas"
id barrio >/dev/null 2>&1 || adduser --system --group --home /opt/barrio --shell /usr/sbin/nologin barrio
mkdir -p /opt/barrio/server /etc/barrio
chown -R barrio:barrio /opt/barrio

echo "==> PostgreSQL (solo escucha en localhost)"
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname = 'barrio'" | grep -q 1; then
  DB_PASSWORD="$(openssl rand -hex 24)"
  sudo -u postgres psql -c "CREATE ROLE barrio LOGIN PASSWORD '${DB_PASSWORD}'"
  sudo -u postgres psql -c "CREATE DATABASE barrio OWNER barrio"
else
  DB_PASSWORD=""
fi

echo "==> Configuración del backend (${ENV_FILE})"
if [[ ! -f "$ENV_FILE" ]]; then
  if [[ -z "$DB_PASSWORD" ]]; then
    echo "El rol 'barrio' ya existe pero falta ${ENV_FILE}. Crear el archivo a mano con su DATABASE_URL." >&2
    exit 1
  fi
  cat > "$ENV_FILE" <<EOF
NODE_ENV=production
HOST=127.0.0.1
PORT=3000
TRUST_PROXY=true
DATABASE_URL=postgres://barrio:${DB_PASSWORD}@127.0.0.1:5432/barrio
JWT_SECRET=$(openssl rand -base64 48 | tr -d '\n')
SERVER_API_KEY=$(openssl rand -hex 32)
AUTH_DEV_MODE=false
EOF
  chown root:barrio "$ENV_FILE"
  chmod 640 "$ENV_FILE"
  echo "    Secretos generados. SERVER_API_KEY es la clave que usará el servidor de juego."
fi

echo "==> Backend: compilar e instalar servicio"
chown -R barrio:barrio "$REPO_DIR"
sudo -u barrio bash -c "cd '$REPO_DIR/backend' && npm ci && npm run build"
cp "$REPO_DIR/infra/vps/backend/barrio-backend.service" /etc/systemd/system/
cp "$REPO_DIR/infra/vps/barrio-server.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now barrio-backend

echo "==> HTTPS para ${API_DOMAIN}"
if [[ -f /etc/caddy/Caddyfile && ! -f /etc/caddy/Caddyfile.original ]]; then
  cp /etc/caddy/Caddyfile /etc/caddy/Caddyfile.original
fi
sed "s/api.facundofr.com/${API_DOMAIN}/" "$REPO_DIR/infra/vps/backend/Caddyfile" > /etc/caddy/Caddyfile
systemctl reload caddy || systemctl restart caddy

echo "==> Firewall"
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 7777/udp
ufw --force enable

echo "==> Comprobación"
sleep 3
curl -fsS http://127.0.0.1:3000/health && echo
echo "Listo. Probar desde afuera: curl https://${API_DOMAIN}/health"
echo "(El certificado HTTPS se emite solo en el primer pedido; el DNS de ${API_DOMAIN} tiene que apuntar a este VPS.)"
