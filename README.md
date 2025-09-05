# pvpn

**Headless ProtonVPN WireGuard CLI** with built-in qBittorrent-nox port-forwarding and reversible kill-switch—designed for Raspberry Pi OS Bookworm (Debian 12) on a Pi 5.

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
   - [list](#pvpn-list)
   - [Command & Flag Aliases](#command--flag-aliases)
7. [Uninstallation](#uninstallation)
8. [Logging & Verbose](#logging--verbose)
9. [Testing](#testing)
10. [Statement of Requirements](#statement-of-requirements)
11. [References](#references)

---

## Features

- **WireGuard VPN**: automatically download & rotate ProtonVPN WireGuard configs  
- **Server Filters**: by country (`--cc`), SecureCore (`--sc`), P2P (`--p2p`), load threshold (`--threshold`)  
- **Fastest-by-RTT**: choose lowest-latency via ICMP (`ping`) or ProtonVPN API (`--fastest api`), or early exit under `--latency-cutoff`  
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
## Quick Start

1. Clone the repository and run the installer:

   ```bash
   git clone https://github.com/you/pvpn.git
   cd pvpn
   sudo ./install.sh
   ```

   The script installs required system packages, creates a Python virtual environment under `/opt/pvpn/venv`, writes a `/usr/local/bin/pvpn` wrapper, registers the `pvpn.service` unit, and prepares `/root/.pvpn-cli/pvpn` for configuration.

2. Initialize pvpn:

   ```bash
   sudo pvpn init
   ```

   Follow the prompts to enter ProtonVPN credentials, qBittorrent settings, and network defaults. This creates `/root/.pvpn-cli/pvpn/config.ini`.

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

Run `pvpn init` to create or update your configuration file:

```bash
pvpn init
pvpn init --proton    # only ProtonVPN credentials
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

Run unit and integration tests:

```bash
cd pvpn
pytest -q
```

- **Unit tests** cover config I/O and CLI parsing.  
- **Integration test** (mocked) simulates full connect/disconnect/list workflow.

---

## Statement of Requirements

Below is a **complete, unambiguous Statement of Requirements** for `pvpn`—a headless (no-GUI) Raspberry Pi OS (Bookworm) CLI client that seamlessly combines ProtonVPN WireGuard, NAT‐PMP port‐forwarding, qBittorrent-nox integration, routing controls (kill-switch), and a fully modular `init` workflow. As an expert developer, take this spec and implement a production-ready solution without missing any critical detail:

---

## 1. Platform & Dependencies

- **OS:** Raspberry Pi OS Bookworm (Debian 12), headless (no desktop).  
- **Language & Tools:**  
  - **Python 3.10+** (CLI via `argparse` or `click`)  
  - Shell tools: `wg`, `ip` (iproute2), `iptables` (or `nftables`), `natpmpc`, `ping`, `curl`, `jq`  
  - **qBittorrent-nox** with optional WebUI API  

---

## 2. Directory Layout & Config Files

- **Base config dir:** `~/.pvpn-cli/pvpn/`  
  - `config.ini` — all persistent settings (INI format, grouped by section)  
  - `wireguard/` — downloaded ProtonVPN `.conf` files  
  - `pvpn.log` — operation logs  

---

## 3. `pvpn init`: Modular Configuration

**Usage:**  
```bash
pvpn init [--proton] [--qb] [--network]
```

- **Global flags:**  
  - `--proton`      ⇒ configure ProtonVPN settings  
  - `--qb`          ⇒ configure qBittorrent-nox settings  
  - `--network`     ⇒ configure kill-switch / DNS defaults
  - If none of the above are passed, run full interactive setup for **all** components.

- **When `--proton`:** prompt or accept:  
  - `--proton-user USER`  
  - `--proton-pass PASS`  
  - `--proton-2fa CODE` (optional)  
  - `--wireguard-port PORT` (default 51820)  
  - `--session-dir DIR` (path to store session tokens; default: `~/.pvpn-cli/pvpn/`)  

- **When `--qb`:** prompt or accept:  
  - `--qb-enable true|false` (enable WebUI API; default true)  
  - `--qb-url URL` (e.g. `http://127.0.0.1:8080`)  
  - `--qb-user USER`  
  - `--qb-pass PASS`  


- **When `--network`:** prompt or accept:  
  - `--ks-default true|false` (kill-switch default on connect; default false)  
  - `--dns-default true|false` (use Proton DNS by default; default true)  
  - `--threshold-default INT` (server-load threshold, 1–100; default 60)  

All values are written to `config.ini` under sections `[protonvpn]`, `[qbittorrent]`, and `[network]`.

---

## 4. Core Commands

### 4.1 `pvpn connect` (`pvpn c`)

```bash
pvpn connect \
  [--cc COUNTRY]    [--sc]      [--p2p]      \
  [--fastest ping|api]            [--threshold INT]  \
  [--dns true|false]              [--ks true|false]
```

- **--cc, -c** Two-letter country code (e.g. `AU`).  
- **--sc** SecureCore servers only (multi-hop).  
- **--p2p** P2P servers only (for port-forwarding).  
- **--fastest, -f** `ping` or `api` (default `ping`).  
- **--threshold, -t** Max server-load %, 1–100 (default from config).  
- **--dns** Switch to Proton DNS? (default from config).  
- **--ks** Enable iptables kill-switch? (default from config).

**Behavior:**  
1. **Authenticate & download** (if needed) all WireGuard `.conf` into `wireguard/`.  
2. **Filter** available configs by `cc`/`sc`/`p2p` & load ≤ threshold.  
3. **Select** best server via ICMP ping or API latency/load.  
4. **Bring up** interface `wgp<cc>`:  
   ```sh
   ip link add dev wgp<cc> type wireguard
   wg setconf wgp<cc> wireguard/<filename>.conf
   ip addr add <Address>/32 peer <Gateway> dev wgp<cc>
   ip link set up dev wgp<cc>
   ```
5. **DNS change**: if `--dns true`, back up `/etc/resolv.conf` and write Proton DNS.  
6. **Kill-switch**: if `--ks true`,  
   ```sh
   iptables-save > pvpn-iptables.bak
   iptables -P OUTPUT DROP
   iptables -A OUTPUT -o wgp<cc> -j ACCEPT
   iptables -A OUTPUT -o lo    -j ACCEPT
   ```
7. **Port-forwarding**:  
   - Run `natpmpc -g <VPN_GATEWAY>` to request a random external port; loop to renew lease.  
   - On failure, fallback to parsing ProtonVPN log entries for `Port pair ...`.  
8. **qBittorrent update**:  
   - If WebUI enabled,  
     ```sh
     curl -X POST -H "Content-Type: application/json" \
       -d '{"listen_port":PORT,"upnp":false,"random_port":false}' \
       ${QB_URL}/api/v2/app/setPreferences
     ```  
   - Else log a warning and skip the port update.
   - Afterward, wait ≤2 min; if no active downloads, call WebUI `/torrents/resumeAll` or `qbittorrentapi` to resume.

### 4.2 `pvpn disconnect` (`pvpn d`)

```bash
pvpn disconnect [--ks true|false]
```

- **--ks** If `false`, restore original `iptables` rules from `pvpn-iptables.bak`; if `true`, leave DROP rules in place.  
- **Teardown**:  
  ```sh
  ip link set down wgp<cc>
  ip link del wgp<cc>
  mv /etc/resolv.conf.pvpnbak /etc/resolv.conf
  ```

### 4.3 `pvpn status` (`pvpn s`)

- Displays:  
  - Interface name, peer IP, last handshake, data in/out  
  - Active DNS server  
  - Kill-switch state  
  - Current server ID/name  
  - Forwarded port & expiry  
  - qBittorrent listen port & active torrent count  

### 4.4 `pvpn list`

```bash
pvpn list [--cc COUNTRY] [--sc] [--p2p] [--fastest ping|api] [--threshold INT]
```

- Lists all available servers matching filters, optionally sorted by latency.

---

## 5. Developer Guidance

- **Idempotency:** repeated commands must clean up previous state.  
- **Error handling:** clear exit codes & messages on login failures, no servers, NAT-PMP errors, API errors.  
- **Logging:** verbose logs to `pvpn.log`; `--verbose` flag for console.  
- **Testing:** include unit tests for argument parsing, mock API calls, and integration tests on a Pi.  

---

## 6. Additional Supporting Research

This section includes research on the latest ProtonVPN documentation and reputable GitHub scripts to validate and refine the specification.
The research seeks to be fully aligned with the current ProtonVPN capabilities, NAT-PMP handling, port forwarding, authentication, kill-switch practices, and best practices for headless (CLI-only) Linux environments.

# ProtonVPN WireGuard CLI Client: Requirements

The CLI tool must manage **WireGuard-based** VPN connections via ProtonVPN and integrate with a headless torrent client (qBittorrent-nox). It should run on Raspberry Pi OS (Bookworm/Debian 12) and support all key features reliably. Crucial requirements include selecting ProtonVPN servers by country and purpose, automatic port forwarding, torrent-port updates, routing controls (kill-switch), and modular command-line configuration. All functionality should rely on ProtonVPN’s APIs and standard Linux tools. The detailed requirements are as follows:

## VPN Connection Handling (WireGuard)

- **Server selection:** Allow choosing VPN servers by country, location or IP, and by special categories. In ProtonVPN, **P2P**-friendly servers (for torrenting) are marked with a double-arrow icon, and all such servers support port forwarding ([How to manually set up port forwarding | Proton VPN](https://protonvpn.com/support/port-forwarding-manual-setup?srsltid=AfmBOorzBdAX1CcLOLgh35Sl9GNJMIT0JR8DRqTdwJP-UbC2deWr1VZC#:~:text=Step%201%3A%20Download%20OpenVPN%20or,WireGuard%20configuration%20files)). The CLI should filter for P2P servers when needed (e.g. for NAT-PMP forwarding) and also support “SecureCore” (multi-hop) servers if requested. By default, use ProtonVPN’s **WireGuard** configs (OpenVPN will be deprecated) ([GitHub - Rafficer/linux-cli-community: Linux command-line client for ProtonVPN. Written in Python.](https://github.com/Rafficer/linux-cli-community#:~:text=Deprecation%20notice)). 

- **Fastest-server algorithm:** Include an option to automatically pick the lowest-latency or least-loaded server. This can be done by measuring round-trip time to candidates (e.g. via `ping`) or by querying ProtonVPN’s server API. Proton’s `/vpn/logicals` API endpoint provides real-time latency and load data for each server ([Supercharge Your headless (Raspberry Pi) VPN with ProtonVPN and WireGuard](https://www.allsubjectsmatter.nl/supercharge-your-headless-raspberry-pi-vpn-with-protonvpn-and-wireguard/#:~:text=checks%20the%20latency%20and%20load,This%20script%20also)), as used in community scripts for headless Pi setups ([Supercharge Your headless (Raspberry Pi) VPN with ProtonVPN and WireGuard](https://www.allsubjectsmatter.nl/supercharge-your-headless-raspberry-pi-vpn-with-protonvpn-and-wireguard/#:~:text=checks%20the%20latency%20and%20load,This%20script%20also)) ([Supercharge Your headless (Raspberry Pi) VPN with ProtonVPN and WireGuard](https://www.allsubjectsmatter.nl/supercharge-your-headless-raspberry-pi-vpn-with-protonvpn-and-wireguard/#:~:text=This%20Python%20script%20automates%20the,entire%20process%20for%20easier%20troubleshooting)). The tool should compare servers (within a chosen country or region) and update the WireGuard configuration to the best-performing server.

- **WireGuard configuration:** Automate downloading or generating a WireGuard key/config from the ProtonVPN account (e.g. via Proton’s web API). ProtonVPN requires an **auth token** (cookie) from login (via their web login form) to retrieve configs, which expire after about 24 hours ([Generate lots of Wireguard configuration for your ProtonVPN Account. · GitHub](https://gist.github.com/fusetim/1a1ee1bdf821a45361f346e9c7f41e5a?permalink_comment_id=5089829#:~:text=%40executed%20That%20is%20correct%2C%20the,the%20particular%20endpoint%20for%20that)). The tool should securely handle login (username, password, 2FA if applicable), store session tokens, and refresh them as needed. Once obtained, the WireGuard config file (e.g. `protonvpn.conf`) must have **NAT-PMP (port forwarding) enabled** and any other options (NetShield, VPN Accelerator) as chosen ([How to manually set up port forwarding | Proton VPN](https://protonvpn.com/support/port-forwarding-manual-setup?srsltid=AfmBOorzBdAX1CcLOLgh35Sl9GNJMIT0JR8DRqTdwJP-UbC2deWr1VZC#:~:text=2,PMP%20%28port%20forwarding%29%20is%20enabled)). The CLI will then bring up the VPN using `wg-quick` or equivalent. (Proton’s GUI for this step is shown below.)

 ([Talha Mangarah | How to port forward with Proton VPN and Gluetun (built in NAT-PMP)](https://talhamangarah.com/blog/how-to-port-forward-with-proton-vpn-and-gluetun/))*Figure: ProtonVPN account dashboard for generating a WireGuard configuration. Users can toggle options like **NAT-PMP (Port Forwarding)** or **VPN Accelerator** before downloading the config* ([How to manually set up port forwarding | Proton VPN](https://protonvpn.com/support/port-forwarding-manual-setup?srsltid=AfmBOorzBdAX1CcLOLgh35Sl9GNJMIT0JR8DRqTdwJP-UbC2deWr1VZC#:~:text=2,PMP%20%28port%20forwarding%29%20is%20enabled)). The CLI should replicate this: select a P2P-capable server (if needed) and ensure NAT-PMP is on for port forwarding.

## NAT-PMP Port Forwarding

- **Protocol support:** After the WireGuard tunnel is up, the tool must request port mappings from ProtonVPN’s server using **NAT-PMP**. ProtonVPN’s WireGuard servers support NAT-PMP only on P2P-flagged servers ([How to manually set up port forwarding | Proton VPN](https://protonvpn.com/support/port-forwarding-manual-setup?srsltid=AfmBOorzBdAX1CcLOLgh35Sl9GNJMIT0JR8DRqTdwJP-UbC2deWr1VZC#:~:text=Step%201%3A%20Download%20OpenVPN%20or,WireGuard%20configuration%20files)) ([How to manually set up port forwarding | Proton VPN](https://protonvpn.com/support/port-forwarding-manual-setup?srsltid=AfmBOorzBdAX1CcLOLgh35Sl9GNJMIT0JR8DRqTdwJP-UbC2deWr1VZC#:~:text=2,PMP%20%28port%20forwarding%29%20is%20enabled)). To leverage this, the CLI should run a NAT-PMP client (e.g. `natpmpc` or a Python NAT-PMP library) to request a random port on the server and map it to the local qBittorrent port. For example, Proton’s docs show installing `natpmpc` and looping it to renew mappings periodically ([How to manually set up port forwarding | Proton VPN](https://protonvpn.com/support/port-forwarding-manual-setup?srsltid=AfmBOorzBdAX1CcLOLgh35Sl9GNJMIT0JR8DRqTdwJP-UbC2deWr1VZC#:~:text=5,Enter)). The tool should do similar: use `natpmpc` (or a Python equivalent like [py-natpmp]) to add a port mapping, and continuously refresh it so it does not expire ([How to manually set up port forwarding | Proton VPN](https://protonvpn.com/support/port-forwarding-manual-setup?srsltid=AfmBOorzBdAX1CcLOLgh35Sl9GNJMIT0JR8DRqTdwJP-UbC2deWr1VZC#:~:text=5,Enter)). If the user’s plan or server selection disallows NAT-PMP, the tool should detect and report that port forwarding is unavailable.

- **qBittorrent port update:** Once a public port is obtained, the CLI must update qBittorrent-nox’s listening port to match using the Web UI (API) bound to localhost:
  ```bash
  curl -X POST -d '{"listen_port": NEW_PORT}' http://localhost:WEBUI_PORT/api/v2/app/setPreferences
  ```
  as shown in qBittorrent’s forums ([Is there a way to change the torrenting port without restarting QBittorrent? - qBittorrent official forums](https://forum.qbittorrent.org/viewtopic.php?t=11385#:~:text=Hi%20i%20do%20change%20the,port%20as%20follows)). The `random_port` option should be disabled via a similar API call. If the Web UI is not available (or locked down), the port update is skipped. Ensure qBittorrent’s UPnP/NAT-PMP feature is disabled to avoid conflicts with the VPN’s port-forward.

## Kill-Switch and Routing Controls

- **Default (full-tunnel):** By default, all traffic from the system should be routed through the VPN tunnel interface (e.g. `wg0`). The tool must configure the system routing table accordingly (e.g. setting VPN as the default route) upon connect.

- **Optional Kill-Switch:** Provide an optional *iptables-based kill switch* that blocks all non-VPN traffic. Practically, this means setting iptables policies to drop OUTPUT to all but the loopback and the VPN interface. For example, one might run `iptables -P OUTPUT DROP` and then `iptables -A OUTPUT -o wg0 -j ACCEPT` (and similar for INPUT/LOOPBACK) ([What is a kill switch? | Proton VPN](https://protonvpn.com/support/what-is-kill-switch?srsltid=AfmBOorRVdj3d2_krw8_3fBHGnUJxi8kftpUM1ngwJFfMdd3Y-jZtv5e#:~:text=A%20kill%20switch%20is%20a,In%20case%20the)). The tool should record/backup the original iptables state so it can restore (disable the kill switch) later. This advanced kill switch ensures **no traffic leaks** if the VPN drops ([What is a kill switch? | Proton VPN](https://protonvpn.com/support/what-is-kill-switch?srsltid=AfmBOorRVdj3d2_krw8_3fBHGnUJxi8kftpUM1ngwJFfMdd3Y-jZtv5e#:~:text=A%20kill%20switch%20is%20a,In%20case%20the)). (Note: Proton’s desktop “Advanced Kill Switch” has similar behavior ([What is a kill switch? | Proton VPN](https://protonvpn.com/support/what-is-kill-switch?srsltid=AfmBOorRVdj3d2_krw8_3fBHGnUJxi8kftpUM1ngwJFfMdd3Y-jZtv5e#:~:text=A%20kill%20switch%20is%20a,In%20case%20the)).) The kill-switch must be reversible: include a command like `pvpn killswitch off` or run on disconnect to reset iptables.


## qBittorrent-nox Integration

- **Web UI API usage:** qBittorrent’s Web UI (bound to localhost) is required for port updates. After obtaining a forwarded port, send an HTTP POST to `/api/v2/app/setPreferences` with JSON `{"listen_port": PORT}` (as demonstrated by the qBittorrent forums ([Is there a way to change the torrenting port without restarting QBittorrent? - qBittorrent official forums](https://forum.qbittorrent.org/viewtopic.php?t=11385#:~:text=Hi%20i%20do%20change%20the,port%20as%20follows))). The WebUI must allow localhost updates (e.g. enable “Bypass authentication for local clients” or set a known token). If the WebUI is disabled, port updates are skipped. Enabling the WebUI may require a one-time manual restart of `qbittorrent-nox`.

## Command-Line Interface Design

  - **Subcommands & argument parsing:** Use a robust CLI framework (e.g. Python’s `argparse` or `click`) with subcommands. The top-level tool might be `pvpn`, with commands like `pvpn init`, `pvpn connect`, `pvpn disconnect`, `pvpn killswitch`, etc. Using `add_subparsers()` in `argparse` is recommended for clarity ([Build Command-Line Interfaces With Python's argparse – Real Python](https://realpython.com/command-line-interfaces-python-argparse/#:~:text=Providing%20subcommands%20in%20your%20CLI,ArgumentParser)). Provide concise help (`-h/--help`) for each option; `argparse` will auto-generate usage messages for user-friendliness ([Build Command-Line Interfaces With Python's argparse – Real Python](https://realpython.com/command-line-interfaces-python-argparse/#:~:text=Great%2C%20now%20your%20program%20automatically,into%20your%20code)). Employ clear option names (e.g. `--country`, `--securecore`) and validate inputs (e.g. check server codes against Proton’s API).

- **Configuration persistence:** Store all settings (credentials, preferred country, P2P preference, qb-webui details, routing choices, etc.) in a persistent config file or files (e.g. under `/etc/pvpn/` or `~/.config/pvpn/`). The `init` command should create/update these in a modular fashion, so `pvpn init --proton` only touches VPN-related settings, etc. Later commands (`connect`) will read these. This design ensures users can easily re-run `init` to change one component without losing others.

## Additional Considerations

- **ProtonVPN API Login:** ProtonVPN does not publish a public REST API for downloading configs; scripts usually mimic web login. The tool should automate login to `account.protonvpn.com` (handling username/password/2FA) to retrieve WireGuard configs or call Proton’s endpoints (like `/vpn/logicals`). Community scripts show this involves capturing cookies like `x-pm-uidauth` ([Generate lots of Wireguard configuration for your ProtonVPN Account. · GitHub](https://gist.github.com/fusetim/1a1ee1bdf821a45361f346e9c7f41e5a?permalink_comment_id=5089829#:~:text=%40executed%20That%20is%20correct%2C%20the,the%20particular%20endpoint%20for%20that)). Since tokens expire daily, the CLI should detect expiry and prompt for re-login or use a headless browser if needed ([Generate lots of Wireguard configuration for your ProtonVPN Account. · GitHub](https://gist.github.com/fusetim/1a1ee1bdf821a45361f346e9c7f41e5a?permalink_comment_id=5089829#:~:text=%40executed%20That%20is%20correct%2C%20the,the%20particular%20endpoint%20for%20that)). Alternatively, let advanced users manually place a valid config file.  

- **System-level setup:** The tool should run as root (or with appropriate privileges) to modify network and iptables. It must work with `iptables` or `nftables` on Bookworm. (On Debian 12, `iptables` commands are generally symlinked to `nft`.) All dependencies (Python 3, `wireguard-tools`, `natpmpc` or similar, `curl`, `iptables`, etc.) should be installable via `apt`.  

- **Integration examples:** Similar solutions exist in the wild. For example, community scripts like **Protonss** (allsubjectsmatter.nl) automate finding the fastest ProtonVPN WireGuard server and switching ([Supercharge Your headless (Raspberry Pi) VPN with ProtonVPN and WireGuard](https://www.allsubjectsmatter.nl/supercharge-your-headless-raspberry-pi-vpn-with-protonvpn-and-wireguard/#:~:text=checks%20the%20latency%20and%20load,This%20script%20also)) ([Supercharge Your headless (Raspberry Pi) VPN with ProtonVPN and WireGuard](https://www.allsubjectsmatter.nl/supercharge-your-headless-raspberry-pi-vpn-with-protonvpn-and-wireguard/#:~:text=This%20Python%20script%20automates%20the,entire%20process%20for%20easier%20troubleshooting)). Docker images (e.g. **Gluetun**) now embed NAT-PMP support for ProtonVPN ([Talha Mangarah | How to port forward with Proton VPN and Gluetun (built in NAT-PMP)](https://talhamangarah.com/blog/how-to-port-forward-with-proton-vpn-and-gluetun/#:~:text=was%20using%20extensively%20for%20qBittorrent,but%20you%20may%20still%20find)). These confirm feasibility: ProtonVPN WireGuard with NAT-PMP **works** (with up-to-date tools) ([Talha Mangarah | How to port forward with Proton VPN and Gluetun (built in NAT-PMP)](https://talhamangarah.com/blog/how-to-port-forward-with-proton-vpn-and-gluetun/#:~:text=was%20using%20extensively%20for%20qBittorrent,but%20you%20may%20still%20find)) ([How to manually set up port forwarding | Proton VPN](https://protonvpn.com/support/port-forwarding-manual-setup?srsltid=AfmBOorzBdAX1CcLOLgh35Sl9GNJMIT0JR8DRqTdwJP-UbC2deWr1VZC#:~:text=2,PMP%20%28port%20forwarding%29%20is%20enabled)). The official ProtonVPN-CLI (Python) has recently warned that OpenVPN configs will stop working in March 2025 ([GitHub - Rafficer/linux-cli-community: Linux command-line client for ProtonVPN. Written in Python.](https://github.com/Rafficer/linux-cli-community#:~:text=Deprecation%20notice)), underlining the need for WireGuard support.  

- **Best practices:** Follow standard CLI design: clear help, sane defaults, and safe error handling. For example, report if a requested country has no servers or if NAT-PMP fails. Keep services (qBittorrent) idempotent – e.g. do not reset the port if reconnection yields the same mapping. Logging actions to a file can aid troubleshooting (especially since this is headless). 

In summary, the CLI must fully automate a ProtonVPN+WireGuard setup for Raspberry Pi, including selecting servers, establishing the tunnel, performing NAT-PMP port forwarding, updating qBittorrent, and enforcing optional routing rules. Each feature above is grounded in existing ProtonVPN documentation and community examples ([How to manually set up port forwarding | Proton VPN](https://protonvpn.com/support/port-forwarding-manual-setup?srsltid=AfmBOorzBdAX1CcLOLgh35Sl9GNJMIT0JR8DRqTdwJP-UbC2deWr1VZC#:~:text=Step%201%3A%20Download%20OpenVPN%20or,WireGuard%20configuration%20files)) ([Is there a way to change the torrenting port without restarting QBittorrent? - qBittorrent official forums](https://forum.qbittorrent.org/viewtopic.php?t=11385#:~:text=Hi%20i%20do%20change%20the,port%20as%20follows)) ([What is a kill switch? | Proton VPN](https://protonvpn.com/support/what-is-kill-switch?srsltid=AfmBOorRVdj3d2_krw8_3fBHGnUJxi8kftpUM1ngwJFfMdd3Y-jZtv5e#:~:text=A%20kill%20switch%20is%20a,In%20case%20the)) ([Build Command-Line Interfaces With Python's argparse – Real Python](https://realpython.com/command-line-interfaces-python-argparse/#:~:text=Providing%20subcommands%20in%20your%20CLI,ArgumentParser)). With careful design, this tool can be production-ready on Bookworm.

**Sources:** ProtonVPN support docs and community guides for WireGuard/NAT-PMP ([How to manually set up port forwarding | Proton VPN](https://protonvpn.com/support/port-forwarding-manual-setup?srsltid=AfmBOorzBdAX1CcLOLgh35Sl9GNJMIT0JR8DRqTdwJP-UbC2deWr1VZC#:~:text=Step%201%3A%20Download%20OpenVPN%20or,WireGuard%20configuration%20files)) ([How to manually set up port forwarding | Proton VPN](https://protonvpn.com/support/port-forwarding-manual-setup?srsltid=AfmBOorzBdAX1CcLOLgh35Sl9GNJMIT0JR8DRqTdwJP-UbC2deWr1VZC#:~:text=2,PMP%20%28port%20forwarding%29%20is%20enabled)) ([How to manually set up port forwarding | Proton VPN](https://protonvpn.com/support/port-forwarding-manual-setup?srsltid=AfmBOorzBdAX1CcLOLgh35Sl9GNJMIT0JR8DRqTdwJP-UbC2deWr1VZC#:~:text=5,Enter)); qBittorrent API/forum posts on port updates ([Is there a way to change the torrenting port without restarting QBittorrent? - qBittorrent official forums](https://forum.qbittorrent.org/viewtopic.php?t=11385#:~:text=Hi%20i%20do%20change%20the,port%20as%20follows)) ([API Access and listening port - qBittorrent official forums](https://forum.qbittorrent.org/viewtopic.php?t=7708#:~:text=Post%20%20%20by%20,Nov%2012%2C%202019%206%3A38%20pm)); kill-switch descriptions ([What is a kill switch? | Proton VPN](https://protonvpn.com/support/what-is-kill-switch?srsltid=AfmBOorRVdj3d2_krw8_3fBHGnUJxi8kftpUM1ngwJFfMdd3Y-jZtv5e#:~:text=A%20kill%20switch%20is%20a,In%20case%20the)); Python `argparse` best practices ([Build Command-Line Interfaces With Python's argparse – Real Python](https://realpython.com/command-line-interfaces-python-argparse/#:~:text=Providing%20subcommands%20in%20your%20CLI,ArgumentParser)) ([Build Command-Line Interfaces With Python's argparse – Real Python](https://realpython.com/command-line-interfaces-python-argparse/#:~:text=Great%2C%20now%20your%20program%20automatically,into%20your%20code)); and real-world examples/scripts ([Supercharge Your headless (Raspberry Pi) VPN with ProtonVPN and WireGuard](https://www.allsubjectsmatter.nl/supercharge-your-headless-raspberry-pi-vpn-with-protonvpn-and-wireguard/#:~:text=checks%20the%20latency%20and%20load,This%20script%20also)) ([Talha Mangarah | How to port forward with Proton VPN and Gluetun (built in NAT-PMP)](https://talhamangarah.com/blog/how-to-port-forward-with-proton-vpn-and-gluetun/#:~:text=was%20using%20extensively%20for%20qBittorrent,but%20you%20may%20still%20find)) ([GitHub - Rafficer/linux-cli-community: Linux command-line client for ProtonVPN. Written in Python.](https://github.com/Rafficer/linux-cli-community#:~:text=Deprecation%20notice)).

---

With this spec, as an expert developer use these **exact instructions** for each command, all flags and defaults, file formats, and the reliable, validated methods for authentication, NAT-PMP, iptables kill-switch, and qBittorrent integration—ensuring a comprehensive, production-quality headless VPN/torrent management solution. 
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
