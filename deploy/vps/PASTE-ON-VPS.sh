# ==============================================================
#  STLIX Enterprise Platform -> Hostinger VPS (153.92.209.190)
#  Paste this whole block into the hPanel Browser terminal (as root).
#  Safe: adds NEW nginx vhosts only; vTiger / egygrouphs untouched.
#  Domains (no GoDaddy DNS needed yet - sslip.io resolves to the IP):
#     https://hub.153-92-209-190.sslip.io   -> Hub + platform.html
#     https://gw.153-92-209-190.sslip.io    -> gateway API
#  Later, after adding A records hub/gw -> 153.92.209.190 on GoDaddy:
#     cd /opt/stlix-gateway && HUB_HOST=hub.stlixvalley.com GW_HOST=gw.stlixvalley.com sudo bash deploy/vps/deploy.sh
# ==============================================================
set -e
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq && apt-get install -y -qq git curl >/dev/null

# 1) code — private repo: git will ask for Username (AbdelrhmanAbdelkafy)
#    and Password = a GitHub Personal Access Token (Contents: read)
if [ -d /opt/stlix-gateway/.git ]; then
  cd /opt/stlix-gateway && git pull
else
  git clone https://github.com/AbdelrhmanAbdelkafy/stlix-gateway.git /opt/stlix-gateway
  cd /opt/stlix-gateway
fi

# 2) .env — created from the example; Nama creds are filled next step
[ -f .env ] || cp .env.example .env
sed -i 's/^APP_ENV=.*/APP_ENV=prod/' .env
chmod 600 .env

# 3) deploy (docker + nginx + basic-auth + certbot)
HUB_HOST=hub.153-92-209-190.sslip.io GW_HOST=gw.153-92-209-190.sslip.io bash deploy/vps/deploy.sh

# 4) show the login
echo "=== BASIC AUTH ==="; echo "user: stlix"; echo -n "pass: "; cat /root/.stlix-hub-password
echo "=== health ==="; curl -s -o /dev/null -w "gateway local: %{http_code}\n" http://127.0.0.1:8000/health
curl -s -o /dev/null -w "hub  https: %{http_code}\n" https://hub.153-92-209-190.sslip.io/health
curl -s -o /dev/null -w "gw   https: %{http_code}\n" https://gw.153-92-209-190.sslip.io/health
