#!/usr/bin/env bash
# Put the portal browser on this server, with a screen a person can log in on.
#
#   Xvfb  :99            a virtual screen for a real (headful) Chromium
#   x11vnc               publishes that screen
#   websockify + noVNC   turns it into something a browser can open
#   stlix-portal.service the agent that holds the browser and answers the gateway
#
# Everything binds to 127.0.0.1: the only way in is through the hub, behind its
# login and the `vat` permission. Nothing new is exposed to the internet.
set -euo pipefail

REPO=${REPO:-/opt/stlix-gateway}
PROFILE=${PROFILE:-/opt/stlix-portal-profile}
DISPLAY_NUM=${DISPLAY_NUM:-99}
VNC_PORT=${VNC_PORT:-5900}
WEB_PORT=${WEB_PORT:-6081}
AGENT_PORT=${AGENT_PORT:-8021}

log() { echo -e "\n=== $* ==="; }
die() { echo "FAILED: $*" >&2; exit 1; }

log "1/6 packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq xvfb x11vnc novnc websockify python3-pip fonts-noto-core fonts-noto-color-emoji >/dev/null
python3 -m pip install -q playwright httpx fastapi uvicorn
python3 -m playwright install --with-deps chromium >/dev/null 2>&1 || python3 -m playwright install chromium

log "2/6 profile + key"
mkdir -p "$PROFILE/shots"
KEY=$(grep -E '^ETA_BROWSER_KEY=' "$REPO/.env" | cut -d= -f2- || true)
[ -n "$KEY" ] || die "ETA_BROWSER_KEY missing from $REPO/.env"
ENTS=$(python3 - "$REPO/.env" <<'PY'
import json,sys
line=[l for l in open(sys.argv[1],encoding='utf-8') if l.startswith('ETA_ENTITIES_JSON=')]
print(",".join(e["key"] for e in json.loads(line[0].split("=",1)[1].strip())) if line else "")
PY
)

log "3/6 virtual screen (Xvfb :$DISPLAY_NUM) + x11vnc, localhost only"
cat > /etc/systemd/system/stlix-xvfb.service <<EOF
[Unit]
Description=STLIX virtual screen for the portal browser
[Service]
ExecStart=/usr/bin/Xvfb :${DISPLAY_NUM} -screen 0 1440x900x24 -nolisten tcp
Restart=always
[Install]
WantedBy=multi-user.target
EOF

# -localhost: x11vnc never listens on a public interface. The hub is the door.
cat > /etc/systemd/system/stlix-x11vnc.service <<EOF
[Unit]
Description=STLIX VNC for the portal browser screen
After=stlix-xvfb.service
Requires=stlix-xvfb.service
[Service]
ExecStart=/usr/bin/x11vnc -display :${DISPLAY_NUM} -rfbport ${VNC_PORT} -localhost -forever -shared -nopw -noxdamage
Restart=always
[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/stlix-novnc.service <<EOF
[Unit]
Description=STLIX noVNC bridge
After=stlix-x11vnc.service
Requires=stlix-x11vnc.service
[Service]
ExecStart=/usr/bin/websockify --web=/usr/share/novnc 127.0.0.1:${WEB_PORT} 127.0.0.1:${VNC_PORT}
Restart=always
[Install]
WantedBy=multi-user.target
EOF

log "4/6 the agent"
cat > /etc/systemd/system/stlix-portal.service <<EOF
[Unit]
Description=STLIX portal browser agent
After=stlix-xvfb.service
Requires=stlix-xvfb.service
[Service]
Environment=DISPLAY=:${DISPLAY_NUM}
Environment=ETA_PROFILE_DIR=${PROFILE}
Environment=ETA_SHOTS_DIR=${PROFILE}/shots
Environment=ETA_AGENT_PORT=${AGENT_PORT}
Environment=STLIX_GATEWAY_URL=http://127.0.0.1:8010
Environment=STLIX_ETA_BROWSER_KEY=${KEY}
Environment=ETA_AGENT_ENTITIES=${ENTS}
Environment=ETA_SCRAPE_MINUTES=0
WorkingDirectory=${REPO}/agents/eta-browser
ExecStart=/usr/bin/python3 ${REPO}/agents/eta-browser/agent.py
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
EOF

log "5/6 start"
systemctl daemon-reload
systemctl enable --now stlix-xvfb stlix-x11vnc stlix-novnc stlix-portal >/dev/null
sleep 6

log "6/6 check"
for s in stlix-xvfb stlix-x11vnc stlix-novnc stlix-portal; do
  echo "$s: $(systemctl is-active $s)"
done
echo "agent: $(curl -s -m 20 http://127.0.0.1:${AGENT_PORT}/status | head -c 200)"
echo "novnc: $(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:${WEB_PORT}/vnc.html)"
echo
echo "افتح: https://hub.stlixvalley.com/tools/portal  →  سجّل دخولك على البورتال بنفسك"
