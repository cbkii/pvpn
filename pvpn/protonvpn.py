# pvpn/protonvpn.py

import os
import sys
import json
import time
import subprocess
import logging
import requests

from pvpn.config import Config
from pvpn.utils import run_cmd, check_root

LOGIN_URL = "https://account.protonvpn.com/api/v4/auth/login"
SERVERS_URL = "https://api.protonvpn.ch/vpn/logicals"
WG_DIR = "wireguard"

def login(cfg: Config) -> str:
    """
    Authenticate to ProtonVPN and obtain a fresh token.
    Stores token + timestamp for reuse.
    """
    logging.info("Logging in to ProtonVPN API")
    payload = {
        "Username": cfg.proton_user,
        "Password": cfg.proton_pass,
        "TwoFactorCode": cfg.proton_2fa or ""
    }
    resp = requests.post(LOGIN_URL, json=payload, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    token = data.get("Token")
    if not token:
        logging.error("Login did not return a token")
        sys.exit(1)

    session = {"token": token, "timestamp": time.time()}
    session_file = os.path.join(cfg.session_dir, "token.json")
    try:
        with open(session_file, "w") as f:
            json.dump(session, f)
        logging.debug(f"Saved session token to {session_file}")
    except Exception as e:
        logging.error(f"Failed to write session file: {e}")

    return token

def load_token(cfg: Config) -> str:
    """
    Load a saved token if under 23h old, else re-login.
    """
    session_file = os.path.join(cfg.session_dir, "token.json")
    if os.path.exists(session_file):
        try:
            data = json.loads(open(session_file).read())
            if time.time() - data.get("timestamp", 0) < 23 * 3600:
                return data.get("token")
            logging.info("ProtonVPN token expired; re-authenticating")
        except Exception as e:
            logging.warning(f"Error reading token file: {e}")
    return login(cfg)

def fetch_servers(token: str) -> list:
    """
    Fetch the full server list, including load/latency.
    """
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(SERVERS_URL, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()

def filter_servers(servers, cc=None, sc=False, p2p=False, threshold=60):
    """
    Filter by country code, SecureCore, P2P, and max load.
    """
    out = []
    for s in servers:
        code = s.get("NameCode", "")[-2:].lower()
        if cc and code != cc.lower():
            continue
        if sc and "SecureCore" not in s.get("Features", []):
            continue
        if p2p and "P2P" not in s.get("Features", []):
            continue
        load = s.get("Load") or 100
        if load > threshold:
            continue
        out.append(s)
    return out

def select_fastest(servers, method="ping", cutoff=None):
    """
    Select lowest-latency server, or first under cutoff ms if provided.
    """
    best = None
    best_val = float("inf")
    for s in servers:
        if method == "api":
            val = s.get("Latency") or float("inf")
        else:
            endpoint = s.get("UDP", "")
            ip = endpoint.split(":")[0]
            try:
                out = subprocess.check_output(
                    ["ping", "-c", "2", "-W", "1", ip],
                    stderr=subprocess.DEVNULL,
                    timeout=5
                ).decode()
                stats = next((l for l in out.splitlines() if "rtt min/avg" in l), "")
                val = float(stats.split("/")[4]) if stats else float("inf")
            except subprocess.TimeoutExpired:
                logging.warning(f"Ping to {ip} timed out")
                continue
            except Exception as e:
                logging.debug(f"Ping error {ip}: {e}")
                continue

        # Early exit if meets cutoff
        if cutoff is not None and val < cutoff:
            logging.info(f"Server {s['Name']} under cutoff: {val}ms")
            return s

        if val < best_val:
            best_val, best = val, s

    if not best:
        logging.error("No reachable servers found")
        sys.exit(1)
    return best

def download_configs(cfg: Config, token: str) -> str:
    """
    Download WireGuard configs for all servers to <config_dir>/wireguard.
    """
    wg_path = os.path.join(cfg.config_dir, WG_DIR)
    os.makedirs(wg_path, exist_ok=True)
    servers = fetch_servers(token)
    for s in servers:
        sid = s["ID"]
        code = s["NameCode"].lower()
        url = f"https://api.protonvpn.ch/vpn/config?server_id={sid}&protocol=wireguard"
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            fname = f"wgp{code}{sid}.conf"
            try:
                with open(os.path.join(wg_path, fname), "wb") as f:
                    f.write(resp.content)
            except Exception as e:
                logging.error(f"Failed writing WG config {fname}: {e}")
        else:
            logging.warning(f"Failed to download config for server {sid}")
    return wg_path

def connect(cfg: Config, args):
    """
    High-level connect command:
      - authenticate
      - download configs if needed
      - filter & select server
      - bring up WireGuard
      - apply DNS, kill-switch, NAT-PMP, qBittorrent updates
    """
    check_root()

    token = load_token(cfg)
    wg_path = os.path.join(cfg.config_dir, WG_DIR)
    if not os.path.isdir(wg_path) or not os.listdir(wg_path):
        download_configs(cfg, token)

    servers = fetch_servers(token)
    thr = args.threshold or cfg.network_threshold_default
    flt = filter_servers(servers, args.cc, args.sc, args.p2p, thr)
    if not flt:
        logging.error("No servers match the specified filters")
        sys.exit(1)

    method = args.fastest or "ping"
    cutoff = getattr(args, "latency_cutoff", None)
    server = select_fastest(flt, method=method, cutoff=cutoff)

    # Determine config file name
    code = server["NameCode"].lower()
    sid = server["ID"]
    conf_file = os.path.join(wg_path, f"wgp{code}{sid}.conf")
    if not os.path.isfile(conf_file):
        logging.error(f"WireGuard config {conf_file} not found")
        sys.exit(1)

    from pvpn.wireguard import bring_up
    iface = bring_up(conf_file, dns=(args.dns == "true") if args.dns else cfg.network_dns_default)

    if (args.ks == "true") or (args.ks is None and cfg.network_ks_default):
        from pvpn.routing import enable_killswitch
        enable_killswitch(iface)

    from pvpn.natpmp import start_forward
    pub_port = start_forward(iface)

    from pvpn.qbittorrent import update_port
    if pub_port:
        update_port(cfg, pub_port)
    else:
        logging.warning("Port forwarding unavailable; continuing without it")

    from pvpn.monitor import start_monitor
    start_monitor(cfg, iface)

    port_msg = pub_port if pub_port else 'none'
    print(f"✅ Connected: {server['Name']} on {iface}, forwarded port {port_msg}")

def disconnect(cfg: Config, args):
    """
    High-level disconnect command:
      - optionally disable kill-switch
      - tear down interface
      - restore DNS
    """
    check_root()

    if args.ks == "false":
        from pvpn.routing import disable_killswitch
        disable_killswitch()

    from pvpn.wireguard import bring_down
    bring_down()

    from pvpn.utils import restore_file
    restore_file("/etc/resolv.conf.pvpnbak", "/etc/resolv.conf")

    print("✅ Disconnected")

def status(cfg: Config):
    """Display WireGuard, routing, and qBittorrent status."""
    from pvpn.wireguard import get_active_iface, get_dns_servers
    from pvpn.routing import killswitch_status
    from pvpn.natpmp import get_public_port
    from pvpn.qbittorrent import get_listen_port

    iface = get_active_iface()
    print(f"Interface: {iface if iface else 'none'}")

    dns = get_dns_servers()
    if dns:
        print("DNS: " + ", ".join(dns))
    else:
        print("DNS: unknown")

    ks = killswitch_status()
    print(f"Kill-switch: {'enabled' if ks else 'disabled'}")

    pub_port = get_public_port(iface, cfg.qb_port) if iface else 0
    if pub_port:
        print(f"Forwarded port: {pub_port}")
    else:
        print("Forwarded port: none")

    qb_port = get_listen_port(cfg)
    print(f"qBittorrent port: {qb_port}")

def list_servers(cfg: Config, args):
    """
    List servers matching filters; optionally show fastest.
    """
    token = load_token(cfg)
    servers = fetch_servers(token)
    thr = args.threshold or cfg.network_threshold_default
    flt = filter_servers(servers, args.cc, args.sc, args.p2p, thr)
    if args.fastest:
        srv = select_fastest(flt, method=args.fastest)
        print(json.dumps(srv, indent=2))
    else:
        print(json.dumps(flt, indent=2))
