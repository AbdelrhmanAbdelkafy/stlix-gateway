#!/usr/bin/env bash
# STLIX Enterprise Platform — VPS deploy (Hostinger, Ubuntu/Debian)
# Idempotent. Adds NEW vhosts only; never touches existing sites (vTiger / WordPress / egygrouphs).
# Usage:  sudo bash deploy/vps/deploy.sh            (inside the repo checkout)
# Env overrides: HUB_HOST, GW_HOST, EMAIL, GW_PORT (srv616844: 8010 — 8000 is Portainer), COOKIE_DOMAIN
#
# Login + permissions live INSIDE the gateway (app/auth — PA2/PA3): both hosts are
# plain reverse proxies to it. Users are in data/auth/auth.db (a docker volume, so
# a rebuild keeps them). The first admin is AUTH_BOOTSTRAP_USER/PASSWORD from .env.
set -euo pipefail

HUB_HOST="${HUB_HOST:-hub.stlixvalley.com}"
GW_HOST="${GW_HOST:-gw.stlixvalley.com}"
EMAIL="${EMAIL:-mokafy93@gmail.com}"
REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
GW_PORT="${GW_PORT:-8010}"
COOKIE_DOMAIN="${COOKIE_DOMAIN:-.stlixvalley.com}"
EXTRA_ALIASES="${EXTRA_ALIASES:-hub.153-92-209-190.sslip.io gw.153-92-209-190.sslip.io}"

log(){ printf '\033[1;36m▶ %s\033[0m\n' "$*"; }
die(){ printf '\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }
[ "$(id -u)" = 0 ] || die "run as root: sudo bash deploy/vps/deploy.sh"

log "1/6 inventory — what is already on this server"
{
  echo "hostname: $(hostname)  ip: $(curl -s4 ifconfig.me || true)"
  echo "--- listeners"; ss -tlnp | grep -E ':(80|443|8000|8010|3000|3306|5432|6379) ' || true
  echo "--- web server"; echo "nginx: $(systemctl is-active nginx 2>/dev/null || true)"; echo "apache2: $(systemctl is-active apache2 2>/dev/null || true)"
  echo "--- nginx sites"; ls /etc/nginx/sites-enabled 2>/dev/null || true
  echo "--- apache sites"; ls /etc/apache2/sites-enabled 2>/dev/null || true
  echo "--- docker"; docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}' 2>/dev/null || echo "docker: not installed"
} | tee "$REPO_DIR/deploy/vps/inventory.$(date +%F).txt"

log "2/6 docker"
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sh
fi
docker compose version >/dev/null 2>&1 || apt-get install -y docker-compose-plugin

log "3/6 .env"
cd "$REPO_DIR"
if [ ! -f .env ]; then
  cp .env.example .env
  echo "⚠  .env created from .env.example — fill NAMA_CLIENT_ID / NAMA_CLIENT_SECRET then re-run."
fi
grep -q '^GATEWAY_API_KEY=.\+' .env || sed -i "s/^GATEWAY_API_KEY=.*/GATEWAY_API_KEY=$(openssl rand -hex 24)/" .env
grep -q '^APP_ENV=prod' .env || sed -i 's/^APP_ENV=.*/APP_ENV=prod/' .env
grep -q '^AUTH_COOKIE_DOMAIN=' .env || echo "AUTH_COOKIE_DOMAIN=${COOKIE_DOMAIN}" >> .env
if ! grep -q '^AUTH_BOOTSTRAP_PASSWORD=.\+' .env; then
  # first admin "stlix": reuse the old basic-auth password if this server had one, else generate
  if [ -f /root/.stlix-hub-password ]; then PASS="$(cat /root/.stlix-hub-password)"; else PASS="$(openssl rand -base64 12)"; echo "$PASS" > /root/.stlix-hub-password; chmod 600 /root/.stlix-hub-password; fi
  sed -i '/^AUTH_BOOTSTRAP_PASSWORD=/d' .env
  echo "AUTH_BOOTSTRAP_PASSWORD=${PASS}" >> .env
  echo "🔑 first admin: user=stlix  password in /root/.stlix-hub-password (change it from the admin screen)"
fi
chmod 600 .env
mkdir -p data/auth && chmod 700 data/auth

log "4/6 gateway container (127.0.0.1:${GW_PORT} only — never public)"
cat > docker-compose.prod.yml <<EOF
services:
  gateway:
    build: .
    image: stlix-gateway:latest
    container_name: stlix-gateway
    ports:
      - "127.0.0.1:${GW_PORT}:8000"
    env_file: [.env]
    volumes:
      - ./data/auth:/app/data/auth
    restart: unless-stopped
EOF
docker compose -f docker-compose.prod.yml up -d --build
for i in $(seq 1 30); do curl -sf "http://127.0.0.1:${GW_PORT}/health" >/dev/null && break; sleep 2; done
curl -sf "http://127.0.0.1:${GW_PORT}/health" >/dev/null && echo "gateway: healthy" || die "gateway /health did not come up — docker logs stlix-gateway"

log "5/6 web server vhosts (reverse proxy — login is the gateway's own)"
if systemctl is-active --quiet apache2 && ! systemctl is-active --quiet nginx; then
  # ---- Apache path (vTiger-style servers) ----
  a2enmod -q proxy proxy_http headers rewrite ssl >/dev/null
  cat > /etc/apache2/sites-available/stlix-hub.conf <<EOF
# STLIX hub/gw — HTTP: everything to HTTPS
<VirtualHost *:80>
  ServerName ${HUB_HOST}
  ServerAlias ${GW_HOST} ${EXTRA_ALIASES}
  RewriteEngine On
  RewriteRule ^ https://%{HTTP_HOST}%{REQUEST_URI} [END,NE,R=permanent]
</VirtualHost>
EOF
  # first run: plain :80 vhosts so certbot can validate; it then writes -le-ssl.conf
  if [ ! -f /etc/apache2/sites-available/stlix-hub-le-ssl.conf ]; then
    cat > /etc/apache2/sites-available/stlix-hub.conf <<EOF
<VirtualHost *:80>
  ServerName ${HUB_HOST}
  ServerAlias ${EXTRA_ALIASES}
  ProxyPreserveHost On
  ProxyPass / http://127.0.0.1:${GW_PORT}/
  ProxyPassReverse / http://127.0.0.1:${GW_PORT}/
</VirtualHost>
<VirtualHost *:80>
  ServerName ${GW_HOST}
  ProxyPreserveHost On
  ProxyPass / http://127.0.0.1:${GW_PORT}/
  ProxyPassReverse / http://127.0.0.1:${GW_PORT}/
</VirtualHost>
EOF
  fi
  a2ensite -q stlix-hub >/dev/null; apache2ctl configtest && systemctl reload apache2
  command -v certbot >/dev/null || apt-get install -y certbot python3-certbot-apache >/dev/null
  if [ ! -f /etc/apache2/sites-available/stlix-hub-le-ssl.conf ]; then
    certbot --apache -n --agree-tos -m "$EMAIL" -d "$HUB_HOST" -d "$GW_HOST" --redirect \
      || echo "⚠ certbot failed — DNS A records for $HUB_HOST / $GW_HOST must point here first"
  fi
  CERT_DIR="$(ls -d /etc/letsencrypt/live/* 2>/dev/null | grep -E "${HUB_HOST}|sslip" | head -1 || true)"
  if [ -n "$CERT_DIR" ]; then
    cat > /etc/apache2/sites-available/stlix-hub-le-ssl.conf <<EOF
# STLIX hub/gw — HTTPS reverse proxy to the gateway (generated by deploy/vps/deploy.sh)
<IfModule mod_ssl.c>
<Macro StlixProxy>
  ProxyPreserveHost On
  ProxyPass / http://127.0.0.1:${GW_PORT}/ retry=0 timeout=300
  ProxyPassReverse / http://127.0.0.1:${GW_PORT}/
  RequestHeader set X-Forwarded-Proto "https"
  RequestHeader unset Authorization
  # SSE: never buffer /api/v1/hub/events
  SetEnvIf Request_URI "^/api/v1/hub/events" proxy-sendchunked=1 no-gzip=1
  Header always set Strict-Transport-Security "max-age=31536000"
  SSLCertificateFile ${CERT_DIR}/fullchain.pem
  SSLCertificateKeyFile ${CERT_DIR}/privkey.pem
  Include /etc/letsencrypt/options-ssl-apache.conf
</Macro>
<VirtualHost *:443>
  ServerName ${HUB_HOST}
  Use StlixProxy
</VirtualHost>
<VirtualHost *:443>
  ServerName ${GW_HOST}
  Use StlixProxy
</VirtualHost>
<VirtualHost *:443>
  ServerName $(echo ${EXTRA_ALIASES} | awk '{print $1}')
  ServerAlias ${EXTRA_ALIASES}
  RewriteEngine On
  RewriteCond %{HTTP_HOST} ^hub\. [NC]
  RewriteRule ^ https://${HUB_HOST}%{REQUEST_URI} [R=302,L]
  RewriteRule ^ https://${GW_HOST}%{REQUEST_URI} [R=302,L]
  SSLCertificateFile ${CERT_DIR}/fullchain.pem
  SSLCertificateKeyFile ${CERT_DIR}/privkey.pem
  Include /etc/letsencrypt/options-ssl-apache.conf
</VirtualHost>
</IfModule>
EOF
    a2enmod -q macro >/dev/null; a2ensite -q stlix-hub-le-ssl >/dev/null
    apache2ctl configtest && systemctl reload apache2
  fi
else
  # ---- nginx path ----
  command -v nginx >/dev/null || apt-get install -y nginx >/dev/null
  cat > /etc/nginx/sites-available/stlix-hub.conf <<EOF
server {
  listen 80; listen [::]:80;
  server_name ${HUB_HOST} ${GW_HOST} ${EXTRA_ALIASES};
  client_max_body_size 20m;
  location / {
    proxy_pass http://127.0.0.1:${GW_PORT};
    proxy_set_header Host \$host; proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for; proxy_set_header X-Forwarded-Proto \$scheme;
    proxy_read_timeout 300s; proxy_buffering off;
  }
}
EOF
  ln -sf /etc/nginx/sites-available/stlix-hub.conf /etc/nginx/sites-enabled/stlix-hub.conf
  nginx -t && systemctl reload nginx
  command -v certbot >/dev/null || apt-get install -y certbot python3-certbot-nginx >/dev/null
  certbot --nginx -n --agree-tos -m "$EMAIL" -d "$HUB_HOST" -d "$GW_HOST" --redirect || echo "⚠ certbot failed — DNS A records for $HUB_HOST / $GW_HOST must point here first"
fi

log "6/6 done"
echo "  Hub:      https://${HUB_HOST}/            (login: stlix, pass: /root/.stlix-hub-password)"
echo "  Platform: https://${HUB_HOST}/hub/platform.html"
echo "  Users:    https://${HUB_HOST}/hub/admin.html"
echo "  Gateway:  https://${GW_HOST}/tools/name-builder   /tools/finance-os   /tools/engineer"
echo "  Health:   https://${GW_HOST}/health   |  docker logs -f stlix-gateway"
