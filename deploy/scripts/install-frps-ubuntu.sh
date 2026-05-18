#!/usr/bin/env bash
set -euo pipefail

FRP_VERSION="${FRP_VERSION:-0.68.0}"
ARCH="${ARCH:-amd64}"
TOKEN="${1:-}"

if [[ -z "${TOKEN}" ]]; then
  echo "Usage: sudo bash deploy/scripts/install-frps-ubuntu.sh <strong-frp-token>" >&2
  exit 1
fi

if [[ "${EUID}" -ne 0 ]]; then
  echo "Please run as root, for example with sudo." >&2
  exit 1
fi

tmp_dir="$(mktemp -d)"
trap 'rm -rf "${tmp_dir}"' EXIT

apt-get update
apt-get install -y curl tar nginx python3

curl -L "https://github.com/fatedier/frp/releases/download/v${FRP_VERSION}/frp_${FRP_VERSION}_linux_${ARCH}.tar.gz" \
  -o "${tmp_dir}/frp.tar.gz"
tar -xzf "${tmp_dir}/frp.tar.gz" -C "${tmp_dir}"
install -m 0755 "${tmp_dir}/frp_${FRP_VERSION}_linux_${ARCH}/frps" /usr/local/bin/frps

id -u frp >/dev/null 2>&1 || useradd --system --home /var/lib/frp --shell /usr/sbin/nologin frp
install -d -m 0755 /etc/frp /var/log/frp /var/lib/frp
chown frp:frp /var/log/frp /var/lib/frp

TOKEN="${TOKEN}" python3 - <<'PY'
from pathlib import Path
import os

template = Path("deploy/frp/frps.gmv-livelens.toml.example").read_text(encoding="utf-8")
Path("/etc/frp/frps.toml").write_text(
    template.replace("replace-with-a-strong-random-frp-token", os.environ["TOKEN"]),
    encoding="utf-8",
)
PY
chmod 0640 /etc/frp/frps.toml
chown root:frp /etc/frp/frps.toml

cp deploy/systemd/frps-gmv-livelens.service /etc/systemd/system/frps-gmv-livelens.service
systemctl daemon-reload
systemctl enable --now frps-gmv-livelens
systemctl status frps-gmv-livelens --no-pager
