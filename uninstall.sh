#!/usr/bin/env bash
set -Eeuo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "This uninstaller must be run as root" >&2
  exit 1
fi

if systemctl list-unit-files | grep -q '^pvpn.service'; then
  echo "==> Stopping pvpn service"
  systemctl disable --now pvpn.service >/dev/null 2>&1 || true
fi

if command -v /usr/local/bin/pvpn >/dev/null 2>&1; then
  echo "==> Disconnecting VPN"
  /usr/local/bin/pvpn disconnect --ks false >/dev/null 2>&1 || true
fi

rm -f /etc/systemd/system/pvpn.service
systemctl daemon-reload

rm -f /usr/local/bin/pvpn
rm -rf /opt/pvpn

ROOT_HOME="$(getent passwd root | cut -d: -f6)"
CONFIG_BASE="$ROOT_HOME/.pvpn-cli"
if [[ -d "$CONFIG_BASE" ]]; then
  read -r -p "Remove configuration and state in $CONFIG_BASE? [y/N]: " ans
  if [[ "$ans" =~ ^[Yy]$ ]]; then
    rm -rf "$CONFIG_BASE"
    echo "Removed $CONFIG_BASE"
  else
    echo "Preserved $CONFIG_BASE"
  fi
fi

rm -f /etc/pvpn-iptables.bak /etc/resolv.conf.pvpnbak

echo "==> Network health check"
if ip route get 1.1.1.1 >/dev/null 2>&1; then
  echo "routing: ok"
else
  echo "routing: check failed"
fi
if ping -c1 -W2 1.1.1.1 >/dev/null 2>&1; then
  echo "ping: ok"
else
  echo "ping: failed"
fi
if getent hosts protonvpn.com >/dev/null 2>&1; then
  echo "dns: ok"
else
  echo "dns: failed"
fi

echo "Uninstallation complete."
