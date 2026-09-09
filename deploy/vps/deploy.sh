#!/usr/bin/env bash
# STLIX Enterprise Platform — VPS deploy (Hostinger, Ubuntu/Debian)
# Idempotent. Adds NEW vhosts only; never touches existing sites (vTiger / WordPress / egygrouphs).
# Usage:  sudo bash deploy/vps/deploy.sh            (inside the repo checkout)
# Env overrides: HUB_HOST, GW_HOST, EMAIL, BASIC_USER
set -euo pipefail

HUB_HOST="${HUB_HOST:-hub.stlixvalley.com}"
GW_HOST="${GW_HOST:-gw.stlixvalley.com}"
EMAIL="${EMAIL:-mokafy93@gmail.com}"
BASIC_USER="${BASIC_USER:-stlix}"
REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
GW_PORT="${GW_PORT:-8000}"
HTPASS=/etc/nginx/.htpasswd-stlix

log(){ printf '\033[1;36m▶ %s\033[0m\n' "$*"; }
die(){ printf '\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }
[ "$(id -u)" = 0 ] || die "run as root: sudo bash deploy/vps/deploy.sh"

log "1/7 inventory — what is already on this server"
{
  echo "hostname: $(hostname)  ip: $(curl -s4 ifconfig.me || true)"
  echo "--- listeners"; ss -tlnp | awk 'NR==1||/:(80|443|8000|3000|3306|5432|6379)\b/'
  echo "--- web server"; systemctl is-active nginx 2>/dev/null | sed 's/^/nginx: /'; systemctl is-active apache2 2>/dev/null | sed 's/^/apache2: /'
  echo "--- nginx sites"; ls /etc/nginx/sites-enabled 2>/dev/null || true
  echo "--- apache sites"; ls /etc/apache2/sites-enabled 2>/dev/null || true
  echo "--- docker"; docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}' 2>/dev/null || echo "docker: not installed"
  echo "--- pm2"; (command -v pm2 >/dev/null && pm2 ls) || echo "pm2: none"
} | tee "$REPO_DIR/deploy/vps/inventory.$(date +%F).txt"

log "2/7 docker"
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sh
fi
docker compose version >/dev/null 2>&1 || apt-get install -y docker-compose-plugin

log "3/7 .env"
cd "$REPO_DIR"
if [ ! -f .env ]; then
  cp .env.example .env
  echo "⚠  .env created from .env.example — fill NAMA_CLIENT_ID / NAMA_CLIENT_SECRET / GATEWAY_API_KEY then re-run."
fi
grep -q '^GATEWAY_API_KEY=.\+' .env || sed -i "s/^GATEWAY_API_KEY=.*/GATEWAY_API_KEY=$(openssl rand -hex 24)/" .env
chmod 600 .env

log "4/7 gateway container (127.0.0.1:${GW_PORT} only — never public)"
cat > docker-compose.prod.yml <<EOF
services:
  gateway:
    build: .
    image: stlix-gateway:latest
    container_name: stlix-gateway
    ports:
      - "127.0.0.1:${GW_PORT}:8000"
    env_file: [.env]
    restart: unless-stopped
EOF
docker compose -f docker-compose.prod.yml up -d --build
for i in $(seq 1 30); do curl -sf "http://127.0.0.1:${GW_PORT}/health" >/dev/null && break; sleep 2; done
curl -sf "http://127.0.0.1:${GW_PORT}/health" && echo || die "gateway /health did not come up — docker logs stlix-gateway"

log "5/7 hub static files"
mkdir -p /var/www/stlix-hub
cp -r "$REPO_DIR/deploy/vps/hub/." /var/www/stlix-hub/
chown -R www-data:www-data /var/www/stlix-hub

log "6/7 access gate (HTTP basic auth — until SSO/RBAC lands: PA2/PA3)"
if [ ! -f "$HTPASS" ]; then
  apt-get install -y apache2-utils >/dev/null
  PASS="$(openssl rand -base64 12)"
  htpasswd -cb "$HTPASS" "$BASIC_USER" "$PASS"
  echo "$PASS" > /root/.stlix-hub-password && chmod 600 /root/.stlix-hub-password
  echo "🔑 basic-auth user=$BASIC_USER  password saved in /root/.stlix-hub-password"
fi

log "7/7 web server vhosts"
if systemctl is-active --quiet apache2 && ! systemctl is-active --quiet nginx; then
  # ---- Apache path (vTiger-style servers) ----
  a2enmod proxy proxy_http headers rewrite ssl >/dev/null
  cp "$HTPASS" /etc/apache2/.htpasswd-stlix
  cat > /etc/apache2/sites-available/stlix-hub.conf <<EOF
<VirtualHost *:80>
  ServerName ${HUB_HOST}
  DocumentRoot /var/www/stlix-hub
  <Directory /var/www/stlix-hub>
    AuthType Basic
    AuthName "STLIX"
    AuthUserFile /etc/apache2/.htpasswd-stlix
    Require valid-user
    Options -Indexes
    AllowOverride None
  </Directory>
</VirtualHost>
<VirtualHost *:80>
  ServerName ${GW_HOST}
  <Location />
    AuthType Basic
    AuthName "STLIX"
    AuthUserFile /etc/apache2/.htpasswd-stlix
    Require valid-user
  </Location>
  ProxyPreserveHost On
  ProxyPass / http://127.0.0.1:${GW_PORT}/
  ProxyPassReverse / http://127.0.0.1:${GW_PORT}/
</VirtualHost>
EOF
  a2ensite stlix-hub >/dev/null && apache2ctl configtest && systemctl reload apache2
  command -v certbot >/dev/null || apt-get install -y certbot python3-certbot-apache >/dev/null
  certbot --apache -n --agree-tos -m "$EMAIL" -d "$HUB_HOST" -d "$GW_HOST" || echo "⚠ certbot failed — DNS A records for $HUB_HOST / $GW_HOST must point here first"
else
  # ---- nginx path (default) ----
  command -v nginx >/dev/null || apt-get install -y nginx >/dev/null
  cat > /etc/nginx/sites-available/stlix-hub.conf <<EOF
server {
  listen 80; listen [::]:80;
  server_name ${HUB_HOST};
  root /var/www/stlix-hub; index index.html;
  auth_basic "STLIX"; auth_basic_user_file ${HTPASS};
  add_header X-Frame-Options SAMEORIGIN; add_header X-Content-Type-Options nosniff;
  location / { try_files \$uri \$uri/ =404; }
  location = /health { auth_basic off; return 200 'ok'; }
}
server {
  listen 80; listen [::]:80;
  server_name ${GW_HOST};
  auth_basic "STLIX"; auth_basic_user_file ${HTPASS};
  client_max_body_size 20m;
  location / {
    proxy_pass http://127.0.0.1:${GW_PORT};
    proxy_set_header Host \$host; proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for; proxy_set_header X-Forwarded-Proto \$scheme;
    proxy_read_timeout 120s;
  }
  location = /health { auth_basic off; proxy_pass http://127.0.0.1:${GW_PORT}/health; }
}
EOF
  ln -sf /etc/nginx/sites-available/stlix-hub.conf /etc/nginx/sites-enabled/stlix-hub.conf
  nginx -t && systemctl reload nginx
  command -v certbot >/dev/null || apt-get install -y certbot python3-certbot-nginx >/dev/null
  certbot --nginx -n --agree-tos -m "$EMAIL" -d "$HUB_HOST" -d "$GW_HOST" --redirect || echo "⚠ certbot failed — DNS A records for $HUB_HOST / $GW_HOST must point here first"
fi

log "done"
echo "  Hub:      https://${HUB_HOST}/            (user: ${BASIC_USER}, pass: /root/.stlix-hub-password)"
echo "  Platform: https://${HUB_HOST}/platform.html"
echo "  Gateway:  https://${GW_HOST}/tools/name-builder   /tools/finance-os   /tools/engineer"
echo "  Health:   https://${GW_HOST}/health   |  docker logs -f stlix-gateway"
