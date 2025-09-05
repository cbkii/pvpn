# Uninstalling pvpn

The uninstaller removes files installed by `install.sh` and optionally deletes configuration.

## Removal steps
- Stops and disables `pvpn.service`.
- Runs `pvpn disconnect --ks false` to tear down the VPN and disable the kill-switch.
- Removes `/usr/local/bin/pvpn`, the virtual environment `/opt/pvpn`, and the systemd unit.
- Optionally deletes `/root/.pvpn-cli` when confirmed.
- Cleans up `iptables` and DNS backups if present and runs a basic network health check.

## Uninstall
```bash
sudo ./uninstall.sh
```
You will be prompted before configuration is deleted.
