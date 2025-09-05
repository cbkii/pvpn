#!/usr/bin/env bash
set -Eeuo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "This installer must be run as root" >&2
  exit 1
fi

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/opt/pvpn"
VENV_DIR="$INSTALL_DIR/venv"
PYTHON_BIN="python3"

echo "==> Installing OS packages"
apt-get update
apt-get install -y \
  python3 python3-venv python3-pip \
  wireguard-tools iproute2 iptables natpmpc \
  iputils-ping curl jq ca-certificates >/tmp/apt.log && tail -n 20 /tmp/apt.log

mkdir -p "$INSTALL_DIR"
if [[ ! -d "$VENV_DIR" ]]; then
  echo "==> Creating virtual environment"
  $PYTHON_BIN -m venv "$VENV_DIR"
fi

echo "==> Installing Python dependencies"
"$VENV_DIR/bin/pip" install --upgrade pip >/tmp/pip.log && tail -n 20 /tmp/pip.log
"$VENV_DIR/bin/pip" install -r "$REPO_DIR/requirements.txt" >>/tmp/pip.log && tail -n 20 /tmp/pip.log
"$VENV_DIR/bin/pip" install "$REPO_DIR" >>/tmp/pip.log && tail -n 20 /tmp/pip.log

echo "==> Installing wrapper script"
cat > /usr/local/bin/pvpn <<'WRAP'
#!/usr/bin/env bash
set -e
VENV_DIR="/opt/pvpn/venv"
exec "$VENV_DIR/bin/python" -m pvpn.cli "$@"
WRAP
chmod +x /usr/local/bin/pvpn

echo "==> Installing systemd unit"
install -m 644 -D "$REPO_DIR/systemd/pvpn.service" /etc/systemd/system/pvpn.service
systemctl daemon-reload
systemctl enable pvpn.service >/dev/null 2>&1 || true

ROOT_HOME="$(getent passwd root | cut -d: -f6)"
CONFIG_DIR="$ROOT_HOME/.pvpn-cli/pvpn"
mkdir -p "$CONFIG_DIR"
chown root:root "$CONFIG_DIR"
chmod 700 "$ROOT_HOME/.pvpn-cli" "$CONFIG_DIR" 2>/dev/null || true

echo "Installation complete. Configure with: sudo pvpn init"
