# pvpn

**Headless ProtonVPN WireGuard CLI** with built-in qBittorrent-nox port-forwarding and reversible kill-switch—designed for Raspberry Pi OS Bookworm (Debian 12) on a Pi 5.
For a complete developer specification and requirements, see [SoR.md](SoR.md).


---

## Table of Contents

1. [Features](#features)
2. [Requirements](#requirements)
3. [Quick Start](#quick-start)
4. [Manual Installation](#manual-installation)
5. [Configuration](#configuration)
6. [Usage](#usage)
   - [init](#pvpn-init)
   - [connect / c](#pvpn-connect)
   - [disconnect / d](#pvpn-disconnect)
   - [status / s](#pvpn-status)
   - [Command & Flag Aliases](#command--flag-aliases)
7. [Uninstallation](#uninstallation)
8. [Logging & Verbose](#logging--verbose)
9. [Testing](#testing)
---

## Features

- **WireGuard VPN**: connect using manually provided ProtonVPN WireGuard configs
- **NAT-PMP Port Forwarding**: `natpmpc`-based mapping & automatic lease refresh
- **qBittorrent-nox Integration**: sync listen-port via WebUI API; resume stalled torrents
- **Kill-Switch**: reversible iptables DROP of all non-VPN traffic (`--ks`)
- **Modular init**: `pvpn init [--proton|--qb|--network]` for targeted or full setup
- **Systemd Service**: optional unit file for automatic connection at boot
- **Background Monitor**: auto-reconnect on repeated ping failures or high latency

---

## Requirements

- **OS:** Raspberry Pi OS Bookworm (Debian 12), headless  
- **Python:** 3.10+  
- **System Packages:**  
  ```bash
  sudo apt update && sudo apt install -y \
    python3 python3-venv python3-pip \
    wireguard-tools iproute2 iptables natpmpc \
    ping curl
  ```  
- **Runtime Python Dependencies:**  
  ```text
  requests>=2.25.0,<3.0
  ```  
- **Dev Dependencies (testing/linting):**  
  ```text
  pytest>=7.0
  pytest-mock>=3.0
  flake8>=4.0
  ```  

---
## Quick Start

1. Clone the repository and run the installer:

   ```bash
   git clone https://github.com/cbkii/pvpn.git
   cd pvpn
   sudo ./install.sh
   ```

   The script installs required system packages, creates a Python virtual environment under `/opt/pvpn/venv`, writes a `/usr/local/bin/pvpn` wrapper, registers the `pvpn.service` unit, and prepares `/root/.pvpn-cli/pvpn` for configuration.

2. Initialize pvpn:

   ```bash
   sudo pvpn init
   ```

    Follow the prompts to configure qBittorrent settings and network defaults. This creates `/root/.pvpn-cli/pvpn/config.ini`. Place any WireGuard `.conf` files under `/root/.pvpn-cli/pvpn/wireguard/`.

3. Connect for the first time:

   ```bash
   sudo pvpn connect
   ```

   Check the status with `pvpn status` and disconnect with `pvpn disconnect`.

4. (Optional) Start the systemd service so pvpn connects automatically on boot:

   ```bash
   sudo systemctl start pvpn.service
   ```

---

## Manual Installation

```bash
git clone https://github.com/cbkii/pvpn.git
cd pvpn

# Create & activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install runtime dependencies
pip install -r requirements.txt

# (Optional) Install dev dependencies
pip install -r requirements-dev.txt

# Install the CLI script globally
sudo ln -s "$PWD/pvpn/cli.py" /usr/local/bin/pvpn
sudo chmod +x /usr/local/bin/pvpn
```

---

## Configuration

### 1. Interactive Setup

Run `pvpn init` to create or update your configuration file:

```bash
pvpn init
pvpn init --qb        # only qBittorrent settings
pvpn init --network   # only DNS & kill-switch defaults
```

This will populate:

- **`~/.pvpn-cli/pvpn/config.ini`**

If qBittorrent's WebUI was not previously enabled, `pvpn init --qb` will configure it for localhost and store your credentials. **Restart the `qbittorrent-nox` service once** after setup so the WebUI becomes active. Subsequent port changes are applied via the API without interrupting downloads. If you later disable the WebUI (`enable = false`), pvpn will warn and skip listen-port updates.

### 2. Example `config.ini`

```ini
[protonvpn]
user = your_username
pass = your_password
2fa = 123456
wireguard_port = 51820
session_dir = /home/pi/.pvpn-cli/pvpn

[qbittorrent]
enable = true
url = http://127.0.0.1:8080
user = pipi
pass = qb_pass
port = 6881

[network]
ks_default = false
dns_default = true
threshold_default = 60

[monitor]
interval = 60
failures = 3
latency_threshold = 500
```

#### Environment variables

To avoid persisting sensitive credentials in `config.ini`, set one or more of
the following environment variables before running `pvpn`:

```
PVPN_PROTON_USER, PVPN_PROTON_PASS, PVPN_PROTON_2FA
PVPN_QB_USER, PVPN_QB_PASS
```

Values provided via environment variables take precedence over `config.ini`
and are omitted when the configuration is saved.

### 3. Background Monitor

After `pvpn connect` succeeds, a background thread periodically pings the
connected server. When `failures` consecutive checks either time out or exceed
`latency_threshold` (ms), the client automatically runs a disconnect followed
by a new connection to rotate servers. Control these values in the `[monitor]`
section of `config.ini`:

```
[monitor]
interval = 60            # seconds between checks
failures = 3             # consecutive bad pings before reconnect
latency_threshold = 500  # milliseconds considered too slow

```

---

## Usage

All commands support `-h/--help` for details.

### `pvpn init`

Interactive or scoped setup:

```bash
pvpn init [--proton] [--qb] [--network]
```

### `pvpn connect` (`pvpn c`)

Bring up VPN, DNS, kill-switch, NAT-PMP, qB port update:

```bash
pvpn connect \
  [--config wg0.conf]    # use existing WireGuard config
  [--dns true]           # switch DNS (default true)
  [--ks true]            # enable kill-switch (default from config)
```

**Examples:**

```bash
pvpn c --config wg0.conf
pvpn c --dns false --ks true
```

### `pvpn disconnect` (`pvpn d`)

Tear down VPN & optionally disable kill-switch:

```bash
pvpn disconnect [--ks false]
```

### `pvpn status` (`pvpn s`)

Show interface, DNS, kill-switch, forwarded port, qB port:

```bash
pvpn status
```

### Command & Flag Aliases

### Command & Flag Aliases

**Commands:**
- `pvpn init`
- `pvpn connect` (`pvpn c`)
- `pvpn disconnect` (`pvpn d`)
- `pvpn status` (`pvpn s`)

**Flags:**
| Long option | Short alias | Applies to              |
|-------------|-------------|-------------------------|
| `--dns`     | *(none)*    | `connect`               |
| `--ks`      | *(none)*    | `connect`, `disconnect` |
| `--proton`  | *(none)*    | `init`                  |
| `--qb`      | *(none)*    | `init`                  |
| `--network` | *(none)*    | `init`                  |


---

## Uninstallation

The uninstaller removes the files installed by `install.sh` and can optionally delete configuration.

```bash
sudo ./uninstall.sh
```

It stops and disables `pvpn.service`, runs `pvpn disconnect --ks false` to tear down the VPN and kill-switch, removes `/usr/local/bin/pvpn`, the virtual environment at `/opt/pvpn`, and the systemd unit. You will be prompted before `/root/.pvpn-cli` is deleted. The script also restores any iptables or DNS backups and performs a basic network check.

---

## Logging & Verbose

- **Console**: use `--verbose` to enable debug-level logs.  
- **File**: operations logged to `~/.pvpn-cli/pvpn/pvpn.log` (mode 600).

---

## Testing

Run unit tests:

```bash
cd pvpn
pytest -q
```

- **Unit tests** cover config I/O and CLI parsing.
- **Integration test** (mocked) simulates full connect/disconnect workflow.

