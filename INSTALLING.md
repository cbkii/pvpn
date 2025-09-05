# Installing pvpn

## Requirements
- Debian Bookworm / Raspberry Pi OS
- Root privileges (`sudo`)
- Internet connectivity

## What the installer does
- Installs system packages: `wireguard-tools`, `iproute2`, `iptables`, `natpmpc`, `iputils-ping`, `curl`, `jq`, `ca-certificates`, and Python tools.
- Creates a Python virtual environment under `/opt/pvpn/venv` and installs `pvpn` and its Python dependency `requests`.
- Writes a wrapper script to `/usr/local/bin/pvpn` that launches the CLI via `python -m pvpn.cli`.
- Installs `pvpn.service` into `/etc/systemd/system/` and enables it (not started automatically).
- Creates the configuration directory at `/root/.pvpn-cli/pvpn` for runtime state.

## Installation
```bash
sudo ./install.sh
```
After installation, configure the tool:
```bash
sudo pvpn init
```
This populates `/root/.pvpn-cli/pvpn/config.ini`.

To start the VPN service after configuration:
```bash
sudo systemctl start pvpn.service
```
