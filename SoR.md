Below is a **complete, unambiguous Statement of Requirements** for `pvpn`—a headless (no-GUI) Raspberry Pi OS (Bookworm) CLI client that seamlessly combines ProtonVPN WireGuard, NAT‐PMP port‐forwarding, qBittorrent-nox integration, routing controls (kill-switch & split-tunnel), and a fully modular `init` workflow. As an expert developer, take this spec and implement a production-ready solution without missing any critical detail:

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
  - `tunnel.json` — split-tunnel rules `{ processes:[], pids:[], ips:[] }`  
  - `wireguard/` — downloaded ProtonVPN `.conf` files  
  - `pvpn.log` — operation logs  

---

## 3. `pvpn init`: Modular Configuration

**Usage:**  
```bash
pvpn init [--proton] [--qb] [--tunnel] [--network]
```

- **Global flags:**  
  - `--proton`      ⇒ configure ProtonVPN settings  
  - `--qb`          ⇒ configure qBittorrent-nox settings  
  - `--tunnel`      ⇒ configure split-tunnel defaults  
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

- **When `--tunnel`:** prompt or accept:  
  - `--tunnel-json PATH` (where to store `tunnel.json`; default: `~/.pvpn-cli/pvpn/tunnel.json`)  

- **When `--network`:** prompt or accept:  
  - `--ks-default true|false` (kill-switch default on connect; default false)  
  - `--dns-default true|false` (use Proton DNS by default; default true)  
  - `--threshold-default INT` (server-load threshold, 1–100; default 60)  

All values are written to `config.ini` under sections `[protonvpn]`, `[qbittorrent]`, `[tunnel]`, and `[network]`.  

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
   - Else stop `qbittorrent-nox`, edit `~/.config/qBittorrent/qBittorrent.conf`, set `Connection\Port=PORT`, restart.  
   - After restart, wait ≤2 min; if no active downloads, call WebUI `/torrents/resumeAll` or `qbittorrentapi` to resume.

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

## 5. Split-Tunnel Management

```bash
pvpn tunnel --add|--rm [--process NAME] [--pid PID] [--ip IP]  
pvpn tunnel --edit
```

- **--add / --rm** apply to exactly one of:
  - `--process NAME` (binary name)  
  - `--pid PID`        (numeric process id)  
  - `--ip IP`          (IPv4 or CIDR)  
- **Behavior on connect/disconnect:**  
  - Mark packets in mangle table:  
    ```sh
    iptables -t mangle -A OUTPUT -m owner --pid-owner PID -j MARK --set-mark 1
    iptables -t mangle -A OUTPUT -m string --string "qbittorrent-nox" --algo bm -j MARK --set-mark 1
    iptables -t mangle -A OUTPUT -d IP -j MARK --set-mark 1
    ```
  - Add policy route:  
    ```sh
    ip rule add fwmark 1 table 100
    ip route add default via <MAIN_GW> dev <MAIN_IF> table 100
    ```
- **--edit** opens `tunnel.json` in `$EDITOR`.

---

## 6. Developer Guidance

- **Idempotency:** repeated commands must clean up previous state.  
- **Error handling:** clear exit codes & messages on login failures, no servers, NAT-PMP errors, API errors.  
- **Logging:** verbose logs to `pvpn.log`; `--verbose` flag for console.  
- **Testing:** include unit tests for argument parsing, mock API calls, and integration tests on a Pi.  

---

## 7. Additional Supporting Research

This section includes research on the latest ProtonVPN documentation and reputable GitHub scripts to validate and refine the specification.
The research seeks to be fully aligned with the current ProtonVPN capabilities, NAT-PMP handling, port forwarding, authentication, split-tunnel methods, kill-switch practices, and best practices for headless (CLI-only) Linux environments.

# ProtonVPN WireGuard CLI Client: Requirements

The CLI tool must manage **WireGuard-based** VPN connections via ProtonVPN and integrate with a headless torrent client (qBittorrent-nox). It should run on Raspberry Pi OS (Bookworm/Debian 12) and support all key features reliably. Crucial requirements include selecting ProtonVPN servers by country and purpose, automatic port forwarding, torrent-port updates, routing controls (kill-switch and split-tunnel), and modular command-line configuration. All functionality should rely on ProtonVPN’s APIs and standard Linux tools. The detailed requirements are as follows:

## VPN Connection Handling (WireGuard)

- **Server selection:** Allow choosing VPN servers by country, location or IP, and by special categories. In ProtonVPN, **P2P**-friendly servers (for torrenting) are marked with a double-arrow icon, and all such servers support port forwarding ([How to manually set up port forwarding | Proton VPN](https://protonvpn.com/support/port-forwarding-manual-setup?srsltid=AfmBOorzBdAX1CcLOLgh35Sl9GNJMIT0JR8DRqTdwJP-UbC2deWr1VZC#:~:text=Step%201%3A%20Download%20OpenVPN%20or,WireGuard%20configuration%20files)). The CLI should filter for P2P servers when needed (e.g. for NAT-PMP forwarding) and also support “SecureCore” (multi-hop) servers if requested. By default, use ProtonVPN’s **WireGuard** configs (OpenVPN will be deprecated) ([GitHub - Rafficer/linux-cli-community: Linux command-line client for ProtonVPN. Written in Python.](https://github.com/Rafficer/linux-cli-community#:~:text=Deprecation%20notice)). 

- **Fastest-server algorithm:** Include an option to automatically pick the lowest-latency or least-loaded server. This can be done by measuring round-trip time to candidates (e.g. via `ping`) or by querying ProtonVPN’s server API. Proton’s `/vpn/logicals` API endpoint provides real-time latency and load data for each server ([Supercharge Your headless (Raspberry Pi) VPN with ProtonVPN and WireGuard](https://www.allsubjectsmatter.nl/supercharge-your-headless-raspberry-pi-vpn-with-protonvpn-and-wireguard/#:~:text=checks%20the%20latency%20and%20load,This%20script%20also)), as used in community scripts for headless Pi setups ([Supercharge Your headless (Raspberry Pi) VPN with ProtonVPN and WireGuard](https://www.allsubjectsmatter.nl/supercharge-your-headless-raspberry-pi-vpn-with-protonvpn-and-wireguard/#:~:text=checks%20the%20latency%20and%20load,This%20script%20also)) ([Supercharge Your headless (Raspberry Pi) VPN with ProtonVPN and WireGuard](https://www.allsubjectsmatter.nl/supercharge-your-headless-raspberry-pi-vpn-with-protonvpn-and-wireguard/#:~:text=This%20Python%20script%20automates%20the,entire%20process%20for%20easier%20troubleshooting)). The tool should compare servers (within a chosen country or region) and update the WireGuard configuration to the best-performing server.

- **WireGuard configuration:** Automate downloading or generating a WireGuard key/config from the ProtonVPN account (e.g. via Proton’s web API). ProtonVPN requires an **auth token** (cookie) from login (via their web login form) to retrieve configs, which expire after about 24 hours ([Generate lots of Wireguard configuration for your ProtonVPN Account. · GitHub](https://gist.github.com/fusetim/1a1ee1bdf821a45361f346e9c7f41e5a?permalink_comment_id=5089829#:~:text=%40executed%20That%20is%20correct%2C%20the,the%20particular%20endpoint%20for%20that)). The tool should securely handle login (username, password, 2FA if applicable), store session tokens, and refresh them as needed. Once obtained, the WireGuard config file (e.g. `protonvpn.conf`) must have **NAT-PMP (port forwarding) enabled** and any other options (NetShield, VPN Accelerator) as chosen ([How to manually set up port forwarding | Proton VPN](https://protonvpn.com/support/port-forwarding-manual-setup?srsltid=AfmBOorzBdAX1CcLOLgh35Sl9GNJMIT0JR8DRqTdwJP-UbC2deWr1VZC#:~:text=2,PMP%20%28port%20forwarding%29%20is%20enabled)). The CLI will then bring up the VPN using `wg-quick` or equivalent. (Proton’s GUI for this step is shown below.)

 ([Talha Mangarah | How to port forward with Proton VPN and Gluetun (built in NAT-PMP)](https://talhamangarah.com/blog/how-to-port-forward-with-proton-vpn-and-gluetun/))*Figure: ProtonVPN account dashboard for generating a WireGuard configuration. Users can toggle options like **NAT-PMP (Port Forwarding)** or **VPN Accelerator** before downloading the config* ([How to manually set up port forwarding | Proton VPN](https://protonvpn.com/support/port-forwarding-manual-setup?srsltid=AfmBOorzBdAX1CcLOLgh35Sl9GNJMIT0JR8DRqTdwJP-UbC2deWr1VZC#:~:text=2,PMP%20%28port%20forwarding%29%20is%20enabled)). The CLI should replicate this: select a P2P-capable server (if needed) and ensure NAT-PMP is on for port forwarding.

## NAT-PMP Port Forwarding

- **Protocol support:** After the WireGuard tunnel is up, the tool must request port mappings from ProtonVPN’s server using **NAT-PMP**. ProtonVPN’s WireGuard servers support NAT-PMP only on P2P-flagged servers ([How to manually set up port forwarding | Proton VPN](https://protonvpn.com/support/port-forwarding-manual-setup?srsltid=AfmBOorzBdAX1CcLOLgh35Sl9GNJMIT0JR8DRqTdwJP-UbC2deWr1VZC#:~:text=Step%201%3A%20Download%20OpenVPN%20or,WireGuard%20configuration%20files)) ([How to manually set up port forwarding | Proton VPN](https://protonvpn.com/support/port-forwarding-manual-setup?srsltid=AfmBOorzBdAX1CcLOLgh35Sl9GNJMIT0JR8DRqTdwJP-UbC2deWr1VZC#:~:text=2,PMP%20%28port%20forwarding%29%20is%20enabled)). To leverage this, the CLI should run a NAT-PMP client (e.g. `natpmpc` or a Python NAT-PMP library) to request a random port on the server and map it to the local qBittorrent port. For example, Proton’s docs show installing `natpmpc` and looping it to renew mappings periodically ([How to manually set up port forwarding | Proton VPN](https://protonvpn.com/support/port-forwarding-manual-setup?srsltid=AfmBOorzBdAX1CcLOLgh35Sl9GNJMIT0JR8DRqTdwJP-UbC2deWr1VZC#:~:text=5,Enter)). The tool should do similar: use `natpmpc` (or a Python equivalent like [py-natpmp]) to add a port mapping, and continuously refresh it so it does not expire ([How to manually set up port forwarding | Proton VPN](https://protonvpn.com/support/port-forwarding-manual-setup?srsltid=AfmBOorzBdAX1CcLOLgh35Sl9GNJMIT0JR8DRqTdwJP-UbC2deWr1VZC#:~:text=5,Enter)). If the user’s plan or server selection disallows NAT-PMP, the tool should detect and report that port forwarding is unavailable.

- **qBittorrent port update:** Once a public port is obtained, the CLI must update qBittorrent-nox’s listening port to match. If the Web UI (API) is enabled for localhost, use its `/api/v2/app/setPreferences` endpoint. For instance:  
  ```bash
  curl -X POST -d '{"listen_port": NEW_PORT}' http://localhost:WEBUI_PORT/api/v2/app/setPreferences
  ```  
  as shown in qBittorrent’s forums ([Is there a way to change the torrenting port without restarting QBittorrent? - qBittorrent official forums](https://forum.qbittorrent.org/viewtopic.php?t=11385#:~:text=Hi%20i%20do%20change%20the,port%20as%20follows)). (The `random_port` option should be disabled via a similar API call.) If the Web UI is not available (or locked down), fall back to editing the qBittorrent configuration file (e.g. `~/.config/qBittorrent/qBittorrent.conf`), replacing the `Connection\Port=` entry and restarting the daemon ([API Access and listening port - qBittorrent official forums](https://forum.qbittorrent.org/viewtopic.php?t=7708#:~:text=Post%20%20%20by%20,Nov%2012%2C%202019%206%3A38%20pm)). In either case, ensure qBittorrent’s UPnP/NAT-PMP feature is disabled to avoid conflicts with the VPN’s port-forward.

## Kill-Switch and Routing Controls

- **Default (full-tunnel):** By default, all traffic from the system should be routed through the VPN tunnel interface (e.g. `wg0`). The tool must configure the system routing table accordingly (e.g. setting VPN as the default route) upon connect.

- **Optional Kill-Switch:** Provide an optional *iptables-based kill switch* that blocks all non-VPN traffic. Practically, this means setting iptables policies to drop OUTPUT to all but the loopback and the VPN interface. For example, one might run `iptables -P OUTPUT DROP` and then `iptables -A OUTPUT -o wg0 -j ACCEPT` (and similar for INPUT/LOOPBACK) ([What is a kill switch? | Proton VPN](https://protonvpn.com/support/what-is-kill-switch?srsltid=AfmBOorRVdj3d2_krw8_3fBHGnUJxi8kftpUM1ngwJFfMdd3Y-jZtv5e#:~:text=A%20kill%20switch%20is%20a,In%20case%20the)). The tool should record/backup the original iptables state so it can restore (disable the kill switch) later. This advanced kill switch ensures **no traffic leaks** if the VPN drops ([What is a kill switch? | Proton VPN](https://protonvpn.com/support/what-is-kill-switch?srsltid=AfmBOorRVdj3d2_krw8_3fBHGnUJxi8kftpUM1ngwJFfMdd3Y-jZtv5e#:~:text=A%20kill%20switch%20is%20a,In%20case%20the)). (Note: Proton’s desktop “Advanced Kill Switch” has similar behavior ([What is a kill switch? | Proton VPN](https://protonvpn.com/support/what-is-kill-switch?srsltid=AfmBOorRVdj3d2_krw8_3fBHGnUJxi8kftpUM1ngwJFfMdd3Y-jZtv5e#:~:text=A%20kill%20switch%20is%20a,In%20case%20the)).) The kill-switch must be reversible: include a command like `pvpn killswitch off` or run on disconnect to reset iptables.

- **Split-tunnel support:** Even with the kill switch available, the tool should also allow *split tunneling* when the kill switch is disabled. In split mode, the user can specify certain destination IP addresses or subnets that should bypass the VPN (go through the normal gateway). This can be implemented by adding policy routing rules: e.g. use `iptables -t mangle -A OUTPUT -d 1.2.3.4 -j MARK --set-mark 1` and `ip rule add fwmark 1 table 100`, with table 100 routed via the physical NIC (eth0) ([ Kali Linux VPN Split Tunneling: How to Route Traffic Securely ](https://cyfuture.cloud/kb/linux/kali-linux-vpn-split-tunneling#:~:text=sudo%20iptables%20,mark%201)). For specific processes, one can run them in a separate network namespace or use cgroup-based packet marking so only those processes’ traffic uses the main route. (In practice, ProtonVPN’s CLI does not allow kill-switch and split-tunnel simultaneously, so our tool should require the user to disable one before enabling the other.) 

## qBittorrent-nox Integration

- **Web UI API usage:** If the user enables qBittorrent’s Web UI (bound to localhost), the CLI should use the WebAPI to update settings. After obtaining a forwarded port, send an HTTP POST to `/api/v2/app/setPreferences` with JSON `{"listen_port": PORT}` (as demonstrated by the qBittorrent forums ([Is there a way to change the torrenting port without restarting QBittorrent? - qBittorrent official forums](https://forum.qbittorrent.org/viewtopic.php?t=11385#:~:text=Hi%20i%20do%20change%20the,port%20as%20follows))). The user should configure the Web UI to allow localhost updates (e.g. enable “Bypass authentication for local clients” or set a known token). This approach avoids restarting qBittorrent.

- **Config file fallback:** If the WebUI is not active, the tool must edit qBittorrent’s config directly. For example, stop `qbittorrent-nox`, open its config file (often `~/.config/qBittorrent/qBittorrent.conf`), change `Connection\Port=...` to the new port, and restart. (This technique was suggested by qBittorrent developers when APIs fail ([API Access and listening port - qBittorrent official forums](https://forum.qbittorrent.org/viewtopic.php?t=7708#:~:text=Post%20%20%20by%20,Nov%2012%2C%202019%206%3A38%20pm)).) The CLI should locate the config automatically or accept it via an option.

## Command-Line Interface Design

- **Subcommands & argument parsing:** Use a robust CLI framework (e.g. Python’s `argparse` or `click`) with subcommands. The top-level tool might be `pvpn`, with commands like `pvpn init`, `pvpn connect`, `pvpn disconnect`, `pvpn killswitch`, etc. Using `add_subparsers()` in `argparse` is recommended for clarity ([Build Command-Line Interfaces With Python's argparse – Real Python](https://realpython.com/command-line-interfaces-python-argparse/#:~:text=Providing%20subcommands%20in%20your%20CLI,ArgumentParser)). Provide concise help (`-h/--help`) for each option; `argparse` will auto-generate usage messages for user-friendliness ([Build Command-Line Interfaces With Python's argparse – Real Python](https://realpython.com/command-line-interfaces-python-argparse/#:~:text=Great%2C%20now%20your%20program%20automatically,into%20your%20code)). Employ clear option names (e.g. `--country`, `--securecore`, `--split-ip`) and validate inputs (e.g. check server codes against Proton’s API).

- **Configuration persistence:** Store all settings (credentials, preferred country, P2P preference, qb-webui details, routing choices, etc.) in a persistent config file or files (e.g. under `/etc/pvpn/` or `~/.config/pvpn/`). The `init` command should create/update these in a modular fashion, so `pvpn init --proton` only touches VPN-related settings, etc. Later commands (`connect`) will read these. This design ensures users can easily re-run `init` to change one component without losing others.

## Additional Considerations

- **ProtonVPN API Login:** ProtonVPN does not publish a public REST API for downloading configs; scripts usually mimic web login. The tool should automate login to `account.protonvpn.com` (handling username/password/2FA) to retrieve WireGuard configs or call Proton’s endpoints (like `/vpn/logicals`). Community scripts show this involves capturing cookies like `x-pm-uidauth` ([Generate lots of Wireguard configuration for your ProtonVPN Account. · GitHub](https://gist.github.com/fusetim/1a1ee1bdf821a45361f346e9c7f41e5a?permalink_comment_id=5089829#:~:text=%40executed%20That%20is%20correct%2C%20the,the%20particular%20endpoint%20for%20that)). Since tokens expire daily, the CLI should detect expiry and prompt for re-login or use a headless browser if needed ([Generate lots of Wireguard configuration for your ProtonVPN Account. · GitHub](https://gist.github.com/fusetim/1a1ee1bdf821a45361f346e9c7f41e5a?permalink_comment_id=5089829#:~:text=%40executed%20That%20is%20correct%2C%20the,the%20particular%20endpoint%20for%20that)). Alternatively, let advanced users manually place a valid config file.  

- **System-level setup:** The tool should run as root (or with appropriate privileges) to modify network and iptables. It must work with `iptables` or `nftables` on Bookworm. (On Debian 12, `iptables` commands are generally symlinked to `nft`.) All dependencies (Python 3, `wireguard-tools`, `natpmpc` or similar, `curl`, `iptables`, etc.) should be installable via `apt`.  

- **Integration examples:** Similar solutions exist in the wild. For example, community scripts like **Protonss** (allsubjectsmatter.nl) automate finding the fastest ProtonVPN WireGuard server and switching ([Supercharge Your headless (Raspberry Pi) VPN with ProtonVPN and WireGuard](https://www.allsubjectsmatter.nl/supercharge-your-headless-raspberry-pi-vpn-with-protonvpn-and-wireguard/#:~:text=checks%20the%20latency%20and%20load,This%20script%20also)) ([Supercharge Your headless (Raspberry Pi) VPN with ProtonVPN and WireGuard](https://www.allsubjectsmatter.nl/supercharge-your-headless-raspberry-pi-vpn-with-protonvpn-and-wireguard/#:~:text=This%20Python%20script%20automates%20the,entire%20process%20for%20easier%20troubleshooting)). Docker images (e.g. **Gluetun**) now embed NAT-PMP support for ProtonVPN ([Talha Mangarah | How to port forward with Proton VPN and Gluetun (built in NAT-PMP)](https://talhamangarah.com/blog/how-to-port-forward-with-proton-vpn-and-gluetun/#:~:text=was%20using%20extensively%20for%20qBittorrent,but%20you%20may%20still%20find)). These confirm feasibility: ProtonVPN WireGuard with NAT-PMP **works** (with up-to-date tools) ([Talha Mangarah | How to port forward with Proton VPN and Gluetun (built in NAT-PMP)](https://talhamangarah.com/blog/how-to-port-forward-with-proton-vpn-and-gluetun/#:~:text=was%20using%20extensively%20for%20qBittorrent,but%20you%20may%20still%20find)) ([How to manually set up port forwarding | Proton VPN](https://protonvpn.com/support/port-forwarding-manual-setup?srsltid=AfmBOorzBdAX1CcLOLgh35Sl9GNJMIT0JR8DRqTdwJP-UbC2deWr1VZC#:~:text=2,PMP%20%28port%20forwarding%29%20is%20enabled)). The official ProtonVPN-CLI (Python) has recently warned that OpenVPN configs will stop working in March 2025 ([GitHub - Rafficer/linux-cli-community: Linux command-line client for ProtonVPN. Written in Python.](https://github.com/Rafficer/linux-cli-community#:~:text=Deprecation%20notice)), underlining the need for WireGuard support.  

- **Best practices:** Follow standard CLI design: clear help, sane defaults, and safe error handling. For example, report if a requested country has no servers or if NAT-PMP fails. Keep services (qBittorrent) idempotent – e.g. do not reset the port if reconnection yields the same mapping. Logging actions to a file can aid troubleshooting (especially since this is headless). 

In summary, the CLI must fully automate a ProtonVPN+WireGuard setup for Raspberry Pi, including selecting servers, establishing the tunnel, performing NAT-PMP port forwarding, updating qBittorrent, and enforcing optional routing rules. Each feature above is grounded in existing ProtonVPN documentation and community examples ([How to manually set up port forwarding | Proton VPN](https://protonvpn.com/support/port-forwarding-manual-setup?srsltid=AfmBOorzBdAX1CcLOLgh35Sl9GNJMIT0JR8DRqTdwJP-UbC2deWr1VZC#:~:text=Step%201%3A%20Download%20OpenVPN%20or,WireGuard%20configuration%20files)) ([Is there a way to change the torrenting port without restarting QBittorrent? - qBittorrent official forums](https://forum.qbittorrent.org/viewtopic.php?t=11385#:~:text=Hi%20i%20do%20change%20the,port%20as%20follows)) ([What is a kill switch? | Proton VPN](https://protonvpn.com/support/what-is-kill-switch?srsltid=AfmBOorRVdj3d2_krw8_3fBHGnUJxi8kftpUM1ngwJFfMdd3Y-jZtv5e#:~:text=A%20kill%20switch%20is%20a,In%20case%20the)) ([ Kali Linux VPN Split Tunneling: How to Route Traffic Securely ](https://cyfuture.cloud/kb/linux/kali-linux-vpn-split-tunneling#:~:text=sudo%20iptables%20,mark%201)) ([Build Command-Line Interfaces With Python's argparse – Real Python](https://realpython.com/command-line-interfaces-python-argparse/#:~:text=Providing%20subcommands%20in%20your%20CLI,ArgumentParser)). With careful design, this tool can be production-ready on Bookworm. 

**Sources:** ProtonVPN support docs and community guides for WireGuard/NAT-PMP ([How to manually set up port forwarding | Proton VPN](https://protonvpn.com/support/port-forwarding-manual-setup?srsltid=AfmBOorzBdAX1CcLOLgh35Sl9GNJMIT0JR8DRqTdwJP-UbC2deWr1VZC#:~:text=Step%201%3A%20Download%20OpenVPN%20or,WireGuard%20configuration%20files)) ([How to manually set up port forwarding | Proton VPN](https://protonvpn.com/support/port-forwarding-manual-setup?srsltid=AfmBOorzBdAX1CcLOLgh35Sl9GNJMIT0JR8DRqTdwJP-UbC2deWr1VZC#:~:text=2,PMP%20%28port%20forwarding%29%20is%20enabled)) ([How to manually set up port forwarding | Proton VPN](https://protonvpn.com/support/port-forwarding-manual-setup?srsltid=AfmBOorzBdAX1CcLOLgh35Sl9GNJMIT0JR8DRqTdwJP-UbC2deWr1VZC#:~:text=5,Enter)); qBittorrent API/forum posts on port updates ([Is there a way to change the torrenting port without restarting QBittorrent? - qBittorrent official forums](https://forum.qbittorrent.org/viewtopic.php?t=11385#:~:text=Hi%20i%20do%20change%20the,port%20as%20follows)) ([API Access and listening port - qBittorrent official forums](https://forum.qbittorrent.org/viewtopic.php?t=7708#:~:text=Post%20%20%20by%20,Nov%2012%2C%202019%206%3A38%20pm)); kill-switch descriptions ([What is a kill switch? | Proton VPN](https://protonvpn.com/support/what-is-kill-switch?srsltid=AfmBOorRVdj3d2_krw8_3fBHGnUJxi8kftpUM1ngwJFfMdd3Y-jZtv5e#:~:text=A%20kill%20switch%20is%20a,In%20case%20the)); Python `argparse` best practices ([Build Command-Line Interfaces With Python's argparse – Real Python](https://realpython.com/command-line-interfaces-python-argparse/#:~:text=Providing%20subcommands%20in%20your%20CLI,ArgumentParser)) ([Build Command-Line Interfaces With Python's argparse – Real Python](https://realpython.com/command-line-interfaces-python-argparse/#:~:text=Great%2C%20now%20your%20program%20automatically,into%20your%20code)); and real-world examples/scripts ([Supercharge Your headless (Raspberry Pi) VPN with ProtonVPN and WireGuard](https://www.allsubjectsmatter.nl/supercharge-your-headless-raspberry-pi-vpn-with-protonvpn-and-wireguard/#:~:text=checks%20the%20latency%20and%20load,This%20script%20also)) ([Talha Mangarah | How to port forward with Proton VPN and Gluetun (built in NAT-PMP)](https://talhamangarah.com/blog/how-to-port-forward-with-proton-vpn-and-gluetun/#:~:text=was%20using%20extensively%20for%20qBittorrent,but%20you%20may%20still%20find)) ([GitHub - Rafficer/linux-cli-community: Linux command-line client for ProtonVPN. Written in Python.](https://github.com/Rafficer/linux-cli-community#:~:text=Deprecation%20notice)).

---

With this spec, as an expert developer use these **exact instructions** for each command, all flags and defaults, file formats, and the reliable, validated methods for authentication, NAT-PMP, iptables kill-switch, and qBittorrent integration—ensuring a comprehensive, production-quality headless VPN/torrent management solution. 