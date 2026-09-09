# ==============================================================
#  STLIX Enterprise Platform -> Hostinger VPS (153.92.209.190)
#  Paste into the hPanel Browser terminal (as root). Idempotent: re-run = update.
#  Login + permissions are inside the gateway (users: /hub/admin.html).
#     https://hub.stlixvalley.com/            -> Hub (login page first)
#     https://hub.stlixvalley.com/hub/admin.html -> users / roles / permissions
#     https://gw.stlixvalley.com/tools/...    -> gateway tools (same login)
#  Gateway container listens on 127.0.0.1:8010 only (8000 is Portainer).
# ==============================================================
set -e
if [ -d /opt/stlix-gateway/.git ]; then
  cd /opt/stlix-gateway && git pull
else
  git clone git@github.com:AbdelrhmanAbdelkafy/stlix-gateway.git /opt/stlix-gateway   # deploy key: /root/.ssh/stlix_deploy
  cd /opt/stlix-gateway
fi
HUB_HOST=hub.stlixvalley.com GW_HOST=gw.stlixvalley.com GW_PORT=8010 \
  bash deploy/vps/deploy.sh 2>&1 | tee /root/stlix-deploy.log
echo "=== ADMIN ==="; echo "user: stlix"; echo -n "pass: "; cat /root/.stlix-hub-password
curl -s -o /dev/null -w "gateway local : %{http_code}\n" http://127.0.0.1:8010/health
curl -s -o /dev/null -w "hub (no login): %{http_code} -> %{redirect_url}\n" -H "Accept: text/html" https://hub.stlixvalley.com/hub/
