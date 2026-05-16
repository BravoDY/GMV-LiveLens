# Public dashboard deployment

This deployment exposes only the read-only dashboard:

- `https://descente.cloud/dashboard`
- `https://www.descente.cloud/dashboard`

The FastAPI app stays private on `127.0.0.1:8100`. Nginx is the only public entrypoint.

## 1. Server files

Assumed server path:

```bash
/opt/gmv-livelens
```

Copy the project there, create the virtualenv, and install dependencies:

```bash
cd /opt/gmv-livelens
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Create the production env file:

```bash
cp deploy/env.production.example .env.production
python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
```

Put the generated token into `GMV_API_TOKEN` in `.env.production`.

## 2. systemd

Create a service user if needed:

```bash
sudo useradd --system --home /opt/gmv-livelens --shell /usr/sbin/nologin gmv
sudo chown -R gmv:gmv /opt/gmv-livelens
```

Install and start the service:

```bash
sudo cp deploy/systemd/gmv-livelens.service /etc/systemd/system/gmv-livelens.service
sudo systemctl daemon-reload
sudo systemctl enable --now gmv-livelens
sudo systemctl status gmv-livelens
curl -i http://127.0.0.1:8100/api/health
```

## 3. Nginx and HTTPS

Install Nginx and Certbot:

```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx
```

Before enabling the HTTPS config, issue the certificate:

```bash
sudo certbot certonly --nginx -d descente.cloud -d www.descente.cloud
```

Install the Nginx site:

```bash
sudo cp deploy/nginx/gmv-livelens-dashboard.conf /etc/nginx/sites-available/gmv-livelens-dashboard.conf
sudo ln -sf /etc/nginx/sites-available/gmv-livelens-dashboard.conf /etc/nginx/sites-enabled/gmv-livelens-dashboard.conf
sudo nginx -t
sudo systemctl reload nginx
```

## 4. Tencent Cloud firewall

Keep public inbound ports:

- TCP `22` for SSH, preferably restricted to your IP
- TCP `80`
- TCP `443`

Remove public inbound `8000-8100` after Nginx is working.

## 5. Verification

```bash
curl -I http://descente.cloud/dashboard
curl -I https://descente.cloud/dashboard
curl https://descente.cloud/api/dashboard
curl -i -X POST https://descente.cloud/api/dashboard-cache/refresh
curl -I https://descente.cloud/
```

Expected:

- HTTP redirects to HTTPS.
- `/dashboard`, `/api/dashboard`, `/api/dashboard-datasets`, and `/api/health` are reachable.
- `POST /api/dashboard-cache/refresh` returns `403` through Nginx.
- `/` redirects to `/dashboard`; other non-allowlisted paths return `403`.
