# Public read-only dashboard over FRP

This project must keep running on the local Windows machine because it controls
Microsoft Edge. The Tencent Cloud Ubuntu server is only the public entrypoint:

```text
Internet -> Tencent Cloud Nginx -> 127.0.0.1:18100 on Ubuntu -> FRP -> Windows 127.0.0.1:8100
```

Public entrypoints:

- Before ICP filing: `http://124.223.70.233/dashboard`
- After ICP filing and certificate setup: `https://descente.cloud/dashboard`
- After ICP filing and certificate setup: `https://www.descente.cloud/dashboard`

Only the read-only dashboard routes are exposed. Management APIs, Edge control,
task configuration, scheduler controls, and cache refresh are blocked by Nginx.

## 1. Generate one FRP token

Run this on any machine:

```bash
openssl rand -hex 32
```

Use the same token for the server and Windows client.

## 2. Tencent Cloud: install FRP server

On Ubuntu, copy or pull this repository folder, then run from the repository root:

```bash
sudo bash deploy/scripts/install-frps-ubuntu.sh '<same-frp-token>'
```

Expected checks:

```bash
sudo systemctl status frps-gmv-livelens --no-pager
sudo ss -lntp | grep -E ':7000|:18100'
```

Port `7000` is the FRP control port. Port `18100` should bind on
`127.0.0.1` only after the Windows client connects.

## 3. Tencent Cloud: enable HTTP/IP Nginx

Still on Ubuntu, from the repository root:

```bash
sudo bash deploy/scripts/install-nginx-frp-http-ubuntu.sh
```

This enables the pre-filing HTTP config:

- `http://124.223.70.233/dashboard`
- `http://descente.cloud/dashboard` if the domain is allowed to resolve

Tencent Cloud firewall should allow:

- TCP `22` for SSH, preferably restricted to your IP
- TCP `80`
- TCP `443` for later HTTPS
- TCP `7000` for FRP, preferably restricted to the Windows machine's public IP

Do not expose TCP `8000-8100`.

## 4. Windows: install FRP client

On the local Windows machine, from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File deploy\scripts\install-frpc-windows.ps1 -Token '<same-frp-token>'
```

Then start the app and tunnel in two windows:

```bat
第1步_启动GMV服务.bat
第2步_启动公网隧道.bat
```

The first script starts the local FastAPI app at `127.0.0.1:8100`.
The second script keeps the FRP tunnel connected to Tencent Cloud.

## 5. Local production safety settings

Copy `deploy/env.local-public.example` into `.env` or update the existing `.env`
with equivalent values:

```dotenv
GMV_APP_ENV=production
GMV_API_TOKEN=replace-with-a-strong-random-api-token
GMV_REQUIRE_API_TOKEN=true
GMV_CORS_ORIGIN_REGEX=https?://(localhost|127\.0\.0\.1|124\.223\.70\.233|descente\.cloud|www\.descente\.cloud)(:\d+)?
GMV_DEBUG_API_ENABLED=false
GMV_SCHEDULER_AUTOSTART=true
```

This is defense in depth. Public access is primarily restricted by Nginx's
allowlist.

## 6. Verification

On Tencent Cloud:

```bash
curl -i http://127.0.0.1:18100/api/health
curl -I http://124.223.70.233/dashboard
curl -i http://124.223.70.233/api/dashboard
curl -i http://124.223.70.233/api/dashboard-datasets
curl -i -X POST http://124.223.70.233/api/dashboard-cache/refresh
curl -i http://124.223.70.233/api/tasks
```

Expected:

- `/dashboard`, `/api/dashboard`, `/api/dashboard-datasets`, and `/api/health`
  return successful responses.
- `POST /api/dashboard-cache/refresh` returns `403`.
- `/api/tasks` returns `403`.
- Browser access to `http://124.223.70.233/dashboard` refreshes at the normal
  dashboard polling cadence.

## 7. After ICP filing: enable HTTPS domain

First make sure DNS A records point to `124.223.70.233`:

- `descente.cloud`
- `www.descente.cloud`

Then on Ubuntu, from the repository root:

```bash
sudo bash deploy/scripts/enable-nginx-frp-https-ubuntu.sh
```

Expected after this step:

- `http://124.223.70.233/dashboard` continues to work.
- `http://descente.cloud/dashboard` redirects to HTTPS.
- `https://descente.cloud/dashboard` works.
- `https://www.descente.cloud/dashboard` works.

## 8. Operations

Useful commands on Ubuntu:

```bash
sudo systemctl status frps-gmv-livelens --no-pager
sudo journalctl -u frps-gmv-livelens -f
sudo nginx -t
sudo systemctl reload nginx
```

Useful checks on Windows:

```powershell
Test-NetConnection 124.223.70.233 -Port 7000
Invoke-WebRequest http://127.0.0.1:8100/api/health
```
