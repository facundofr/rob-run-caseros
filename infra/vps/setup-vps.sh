#!/usr/bin/env bash
# Prepara el VPS (Ubuntu 22.04 o 24.04) para Barrio: backend, PostgreSQL, HTTPS y servidor de juego.
#
# Pensado para convivir con otros servicios del mismo VPS:
# - Usa su propio Node.js en /opt/barrio/node (no toca el Node del sistema).
# - El backend escucha en 127.0.0.1:${BACKEND_PORT} (3100 por defecto) y falla si el puerto está ocupado.
# - Si ya hay Nginx o Caddy, agrega un sitio nuevo; nunca reemplaza la configuración existente.
# - No activa el firewall si está apagado (solo agrega reglas).
#
# Uso, como root en el VPS:
#   git clone https://github.com/facundofr/rob-run-caseros.git /opt/barrio/repo
#   bash /opt/barrio/repo/infra/vps/setup-vps.sh
# Variables opcionales: API_DOMAIN, GAME_DOMAIN, BACKEND_PORT, CERTBOT_EMAIL.
# Se puede volver a ejecutar: no pisa secretos ni bases existentes.
set -euo pipefail

API_DOMAIN="${API_DOMAIN:-caseros-api.facundofr.com}"
GAME_DOMAIN="${GAME_DOMAIN:-caseros.facundofr.com}"
BACKEND_PORT="${BACKEND_PORT:-3100}"
NODE_VERSION="24.11.1"
REPO_DIR="/opt/barrio/repo"
NODE_DIR="/opt/barrio/node"
ENV_FILE="/etc/barrio/backend.env"
GAME_ENV_FILE="/etc/barrio/gameserver.env"

if [[ $EUID -ne 0 ]]; then
  echo "Ejecutar como root." >&2
  exit 1
fi

is_active() { systemctl is-active --quiet "$1" 2>/dev/null; }

echo "==> Paquetes base"
apt-get update
apt-get install -y curl ca-certificates gnupg git openssl xz-utils postgresql

echo "==> Usuario y carpetas"
id barrio >/dev/null 2>&1 || adduser --system --group --home /opt/barrio --shell /usr/sbin/nologin barrio
mkdir -p /opt/barrio/server /etc/barrio

echo "==> Node.js ${NODE_VERSION} propio en ${NODE_DIR}"
if [[ ! -x "$NODE_DIR/bin/node" || "$("$NODE_DIR/bin/node" -v)" != "v${NODE_VERSION}" ]]; then
  ARCH="$(uname -m)"; [[ "$ARCH" == "x86_64" ]] && ARCH="x64"; [[ "$ARCH" == "aarch64" ]] && ARCH="arm64"
  TARBALL="node-v${NODE_VERSION}-linux-${ARCH}.tar.xz"
  TMP="$(mktemp -d)"
  curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/${TARBALL}" -o "$TMP/$TARBALL"
  curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/SHASUMS256.txt" -o "$TMP/SHASUMS256.txt"
  (cd "$TMP" && grep " ${TARBALL}\$" SHASUMS256.txt | sha256sum -c -)
  rm -rf "$NODE_DIR" && mkdir -p "$NODE_DIR"
  tar -xJf "$TMP/$TARBALL" -C "$NODE_DIR" --strip-components=1
  rm -rf "$TMP"
fi
export PATH="$NODE_DIR/bin:$PATH"

echo "==> PostgreSQL: base 'barrio' (solo localhost)"
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
  if ss -ltn "( sport = :${BACKEND_PORT} )" | grep -q LISTEN; then
    echo "El puerto ${BACKEND_PORT} ya está en uso. Ejecutar con BACKEND_PORT=<otro puerto libre>." >&2
    exit 1
  fi
  cat > "$ENV_FILE" <<EOF
NODE_ENV=production
HOST=127.0.0.1
PORT=${BACKEND_PORT}
TRUST_PROXY=true
DATABASE_URL=postgres://barrio:${DB_PASSWORD}@127.0.0.1:5432/barrio
JWT_SECRET=$(openssl rand -base64 48 | tr -d '\n')
SERVER_API_KEY=$(openssl rand -hex 32)
AUTH_DEV_MODE=false
EOF
  chown root:barrio "$ENV_FILE"
  chmod 640 "$ENV_FILE"
  echo "    Secretos generados."
fi
BACKEND_PORT="$(grep '^PORT=' "$ENV_FILE" | cut -d= -f2)"

echo "==> Configuración del servidor de juego (${GAME_ENV_FILE})"
if [[ ! -f "$GAME_ENV_FILE" ]]; then
  cat > "$GAME_ENV_FILE" <<EOF
BARRIO_BACKEND_URL=http://127.0.0.1:${BACKEND_PORT}
BARRIO_SERVER_KEY=$(grep '^SERVER_API_KEY=' "$ENV_FILE" | cut -d= -f2)
BARRIO_SERVER_NAME=Caseros 1
BARRIO_PUBLIC_ADDRESS=${GAME_DOMAIN}
BARRIO_REGION=sa-east
EOF
  chown root:barrio "$GAME_ENV_FILE"
  chmod 640 "$GAME_ENV_FILE"
fi

echo "==> Backend: compilar e instalar servicio"
chown -R barrio:barrio /opt/barrio
sudo -u barrio env PATH="$PATH" bash -c "cd '$REPO_DIR/backend' && npm ci && npm run build"
cp "$REPO_DIR/infra/vps/backend/barrio-backend.service" /etc/systemd/system/
cp "$REPO_DIR/infra/vps/barrio-server.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable barrio-backend
systemctl restart barrio-backend

echo "==> HTTPS para ${API_DOMAIN} -> 127.0.0.1:${BACKEND_PORT}"
if is_active nginx; then
  echo "    Nginx detectado: se agrega un sitio y el certificado con certbot."
  apt-get install -y certbot python3-certbot-nginx
  sed -e "s/__API_DOMAIN__/${API_DOMAIN}/g" -e "s/__BACKEND_PORT__/${BACKEND_PORT}/g" \
    "$REPO_DIR/infra/vps/backend/nginx-barrio-api.conf" > /etc/nginx/sites-available/barrio-api.conf
  ln -sf /etc/nginx/sites-available/barrio-api.conf /etc/nginx/sites-enabled/barrio-api.conf
  nginx -t
  systemctl reload nginx
  certbot --nginx -d "$API_DOMAIN" --non-interactive --agree-tos --redirect \
    ${CERTBOT_EMAIL:+--email "$CERTBOT_EMAIL"} ${CERTBOT_EMAIL:---register-unsafely-without-email}
elif is_active apache2; then
  echo "Apache ocupa los puertos 80/443. Este script no configura Apache: hay que agregar un proxy a" >&2
  echo "127.0.0.1:${BACKEND_PORT} para ${API_DOMAIN} a mano. El backend ya está corriendo." >&2
  exit 1
else
  CADDY_WAS_INSTALLED=true
  if ! command -v caddy >/dev/null; then
    CADDY_WAS_INSTALLED=false
    apt-get install -y debian-keyring debian-archive-keyring apt-transport-https
    curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/gpg.key | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt > /etc/apt/sources.list.d/caddy-stable.list
    apt-get update
    apt-get install -y caddy
  fi
  sed -e "s/__API_DOMAIN__/${API_DOMAIN}/g" -e "s/__BACKEND_PORT__/${BACKEND_PORT}/g" \
    "$REPO_DIR/infra/vps/backend/Caddyfile" > /etc/caddy/barrio.caddy
  if [[ "$CADDY_WAS_INSTALLED" == false ]]; then
    # Caddy recién instalado: se reemplaza el sitio de ejemplo.
    echo "import /etc/caddy/barrio.caddy" > /etc/caddy/Caddyfile
  elif ! grep -q "import /etc/caddy/barrio.caddy" /etc/caddy/Caddyfile; then
    cp /etc/caddy/Caddyfile "/etc/caddy/Caddyfile.backup-$(date +%Y%m%d%H%M%S)"
    printf '\nimport /etc/caddy/barrio.caddy\n' >> /etc/caddy/Caddyfile
  fi
  caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
  systemctl enable caddy
  systemctl reload caddy || systemctl restart caddy
fi

echo "==> Firewall"
if command -v ufw >/dev/null && ufw status | grep -q "Status: active"; then
  ufw allow 80/tcp
  ufw allow 443/tcp
  ufw allow 7777/udp
else
  echo "    ufw no está activo: no se modifica. Asegurarse de que 80/tcp, 443/tcp y 7777/udp estén abiertos."
fi

echo "==> Comprobación"
for attempt in $(seq 1 15); do
  curl -fsS "http://127.0.0.1:${BACKEND_PORT}/health" >/dev/null && break
  sleep 1
done
curl -fsS "http://127.0.0.1:${BACKEND_PORT}/health" && echo
echo "Listo. Probar desde afuera: curl https://${API_DOMAIN}/health"
echo "(El DNS de ${API_DOMAIN} y ${GAME_DOMAIN} tiene que apuntar a este VPS.)"
