# pvpn

**Headless ProtonVPN WireGuard CLI** with built-in qBittorrent-nox port-forwarding and reversible kill-switch—designed for Raspberry Pi OS Bookworm (Debian 12) on a Pi 5.

---

## Table of Contents

1. [Features](#features)  
2. [Requirements](#requirements)  
3. [Installation](#installation)  
4. [Configuration](#configuration)  
5. [Usage](#usage)  
   - [init](#pvpn-init)  
   - [connect / c](#pvpn-connect)  
   - [disconnect / d](#pvpn-disconnect)  
   - [status / s](#pvpn-status)  
   - [list](#pvpn-list)  
   - [Command & Flag Aliases](#command--flag-aliases)
6. [Logging & Verbose](#logging--verbose)  
7. [Testing](#testing)  
8. [References](#references)  

---

## Features

- **WireGuard VPN**: automatically download & rotate ProtonVPN WireGuard configs  
- **Server Filters**: by country (`--cc`), SecureCore (`--sc`), P2P (`--p2p`), load threshold (`--threshold`)  
- **Fastest-by-RTT**: choose lowest-latency via ICMP (`ping`) or ProtonVPN API (`--fastest api`), or early exit under `--latency-cutoff`  
- **NAT-PMP Port Forwarding**: `natpmpc`-based mapping & automatic lease refresh  
- **qBittorrent-nox Integration**: sync listen-port via WebUI API or config-file fallback; resume stalled torrents  
- **Kill-Switch**: reversible iptables DROP of all non-VPN traffic (`--ks`)
- **Split-Tunnel**: bypass VPN for specific processes, PIDs, or IPs (`pvpn tunnel`)
- **Modular init**: `pvpn init [--proton|--qb|--tunnel|--network]` for targeted or full setup
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
    ping curl jq
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

## Installation

```bash
git clone https://github.com/you/pvpn.git
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

Run `pvpn init` to create or update your configuration files:

```bash
pvpn init
pvpn init --proton    # only ProtonVPN credentials
pvpn init --qb        # only qBittorrent settings
pvpn init --network   # only DNS & kill-switch defaults
```

This will populate:

- **`~/.pvpn-cli/pvpn/config.ini`**

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

[tunnel]
tunnel_json_path = /home/pi/.pvpn-cli/pvpn/tunnel.json

[monitor]
interval = 60
failures = 3
latency_threshold = 500
```

### 3. Example `tunnel.json`

```json
{
  "processes": ["qbittorrent-nox"],
  "pids": [12345],
  "ips": ["203.0.113.0/24"]
}
```

### 4. Background Monitor

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
  [--cc AU]              # country code
  [--sc]                 # SecureCore multi-hop
  [--p2p]                # P2P servers (for port-forward)
  [--fastest ping]       # ping or api (default ping)
  [--threshold 60]       # max server load %
  [--latency-cutoff 100] # first server with ping < 100 ms
  [--dns true]           # switch to Proton DNS (default true)
  [--ks true]            # enable kill-switch (default from config)
```

**Examples:**

```bash
pvpn c --cc US --fastest api --threshold 50
pvpn c --p2p --latency-cutoff 80 --ks true
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

### `pvpn list`

List servers matching filters:

```bash
pvpn list [--cc AU] [--sc] [--p2p] [--fastest ping] [--threshold 60]
```

### Command & Flag Aliases

**Commands:**
- `pvpn init`
- `pvpn connect` (`pvpn c`)
- `pvpn disconnect` (`pvpn d`)
- `pvpn status` (`pvpn s`)
- `pvpn list`

**Flags:**  
| Long option             | Short alias | Applies to                  |
|-------------------------|-------------|-----------------------------|
| `--cc`                  | `-c`        | `connect`, `list`           |
| `--fastest`             | `-f`        | `connect`, `list`           |
| `--threshold`           | `-t`        | `connect`, `list`           |
| `--latency-cutoff`      | `-l`        | `connect`                   |
| `--dns`                 | *(none)*    | `connect`                   |
| `--ks`                  | *(none)*    | `connect`, `disconnect`     |
| `--sc`                  | *(none)*    | `connect`, `list`           |
| `--p2p`                 | *(none)*    | `connect`, `list`           |
| `--proton`              | *(none)*    | `init`                      |
| `--qb`                  | *(none)*    | `init`                      |
| `--network`             | *(none)*    | `init`                      |


---

## Logging & Verbose

- **Console**: use `--verbose` to enable debug-level logs.  
- **File**: operations logged to `~/.pvpn-cli/pvpn/pvpn.log` (mode 600).

---

## Testing

Run unit and integration tests:

```bash
cd pvpn
pytest -q
```

- **Unit tests** cover config I/O and CLI parsing.  
- **Integration test** (mocked) simulates full connect/disconnect/list workflow.

---

## References

1. ProtonVPN Manual Port Forwarding  
   https://protonvpn.com/support/port-forwarding-manual-setup  
2. Headless Pi + WireGuard Tutorial  
   https://www.allsubjectsmatter.nl/supercharge-your-headless-raspberry-pi-vpn-with-protonvpn-and-wireguard/  
3. qBittorrent WebUI API  
   https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-%28qBittorrent-4.1%29  
4. ProtonVPN Advanced Kill-Switch  
   https://protonvpn.com/support/advanced-kill-switch  
5. Policy-Based Routing  
   https://www.privateproxyguide.com/creating-vpn-gateways-with-policy-based-routing-using-iptables-and-nftables/  
6. natpmpc Manual  
   https://man.archlinux.org/man/natpmpc.1.en  
7. Python argparse  
   https://docs.python.org/3/library/argparse.html  
8. ProtonVPN-CLI Deprecation Notice  
   https://github.com/Rafficer/linux-cli-community  
