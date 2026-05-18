#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Please run as root, for example with sudo." >&2
  exit 1
fi

apt-get update
apt-get install -y nginx certbot python3-certbot-nginx

certbot certonly --nginx -d descente.cloud -d www.descente.cloud

install -d -m 0755 /etc/nginx/snippets
cp deploy/nginx/snippets/gmv-livelens-public-locations.conf /etc/nginx/snippets/gmv-livelens-public-locations.conf
cp deploy/nginx/gmv-livelens-frp-https.conf /etc/nginx/sites-available/gmv-livelens-frp-https.conf
rm -f /etc/nginx/sites-enabled/gmv-livelens-frp-http.conf
ln -sf /etc/nginx/sites-available/gmv-livelens-frp-https.conf /etc/nginx/sites-enabled/gmv-livelens-frp-https.conf
rm -f /etc/nginx/sites-enabled/default

nginx -t
systemctl reload nginx
