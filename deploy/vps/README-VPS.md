# الرفع على الـ VPS — hub.stlixvalley.com + gw.stlixvalley.com

> القاعدة من `docs/cloud-repo.md` لسه شغالة: المنصّة ما تتعرضش على الإنترنت من غير بوّابة دخول.
> الحل هنا مؤقت ومقبول لحد ما SSO/RBAC (PA2/PA3) يخلص: **HTTP Basic Auth** على الدومينين،
> والـ gateway نفسه بيسمع على `127.0.0.1:8000` بس — مش مفتوح للعالم.

## اللي بيتركّب على السيرفر (ومش بيلمس vTiger / WordPress / egygrouphs)
| الدومين | بيخدم إيه | من فين |
|---|---|---|
| `hub.stlixvalley.com` | STLIX Hub (الباب الواحد) + `platform.html` (Enterprise Platform) | `/var/www/stlix-hub` — ملفات static |
| `gw.stlixvalley.com` | stlix-gateway (FastAPI في Docker): `/tools/name-builder` `/tools/finance-os` `/tools/engineer` `/api/v1/...` | container `stlix-gateway` |

الاسكربت بيكشف لوحده: nginx ولا apache2 هو اللي شغال، وبيضيف vhosts جديدة بس، وبيعمل HTTPS بـ certbot.

## قبل التشغيل (مرة واحدة)
1. **DNS على GoDaddy** — سجلين A:
   - `hub` → `153.92.209.190`
   - `gw`  → `153.92.209.190`
2. **الكود على السيرفر** — من الريبو الخاص (بعد `github-setup.bat`):
   ```bash
   git clone <private-repo-url> /opt/stlix-gateway
   ```
   أو فك `stlix-vps-bundle.tar.gz` في `/opt/stlix-gateway`.
3. **`.env`** — انسخه بإيدك (مش في الريبو عن قصد):
   ```bash
   cd /opt/stlix-gateway && cp .env.example .env && nano .env
   ```
   المطلوب على الأقل: `NAMA_BASE_URL` `NAMA_CLIENT_ID` `NAMA_CLIENT_SECRET` — والـ `GATEWAY_API_KEY` بيتولد لوحده لو فاضي.

## التشغيل
```bash
cd /opt/stlix-gateway
sudo bash deploy/vps/deploy.sh
```
- الخطوة 1 بتطبع **جرد السيرفر** (إيه اللي شغال على 80/443، docker، pm2) وبتحفظه في `deploy/vps/inventory.<date>.txt` — ده اللي بنملّي منه قائمة الـ Hub.
- باسورد الـ Basic Auth بيتولد وبيتحفظ في `/root/.stlix-hub-password` (user: `stlix`).

## بعد التشغيل
- `https://hub.stlixvalley.com/` → الـ Hub · `/platform.html` → المنصّة
- `https://gw.stlixvalley.com/health` → لازم يرجّع 200
- لوج: `docker logs -f stlix-gateway`
- تحديث: `git pull && docker compose -f docker-compose.prod.yml up -d --build && cp -r deploy/vps/hub/. /var/www/stlix-hub/`

## تغيير الباسورد / إضافة مستخدم
```bash
htpasswd /etc/nginx/.htpasswd-stlix <user>     # nginx
htpasswd /etc/apache2/.htpasswd-stlix <user>   # apache
```
