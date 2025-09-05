# pvpn/natpmp.py

"""
Handle NAT-PMP port forwarding via `natpmpc` for a given WireGuard interface.
Requests a mapping from the VPN gateway to the local qBittorrent port,
then periodically refreshes the lease.
"""

import os
import re
import subprocess
import threading
import time
import logging
from pathlib import Path

from pvpn.config import Config
from pvpn.utils import run_cmd, check_root

# Interval (in seconds) to refresh the NAT-PMP lease
REFRESH_INTERVAL = 50

def _get_vpn_gateway(iface: str) -> str:
    """
    Determine the VPN gateway IP for the given interface by parsing:
      ip route show dev <iface> | grep default
    """
    try:
        out = run_cmd(f"ip route show dev {iface} | grep default")
        parts = out.split()
        gw = parts[parts.index("via") + 1]
        return gw
    except Exception as e:
        logging.error(f"Failed to get VPN gateway for interface {iface}: {e}")
        raise

def _request_mapping(gateway: str, internal_port: int) -> int:
    """
    Use `natpmpc` to request a port mapping for internal_port.
    Returns the external (public) port, or 0 on failure.
    """
    cmd = ["natpmpc", "-g", gateway, str(internal_port)]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=10).decode()
        for line in out.splitlines():
            if "Mapped public port" in line:
                return int(line.strip().split()[-1])
        logging.error(f"No mapping found in natpmpc output:\n{out}")
    except subprocess.TimeoutExpired:
        logging.error("natpmpc request timed out")
    except subprocess.CalledProcessError as e:
        logging.error(f"natpmpc failed: {e.output.decode().strip()}")
    except Exception as e:
        logging.error(f"Unexpected error calling natpmpc: {e}")
    return 0


def _parse_port_from_log(log_path: str) -> int:
    """Scan the pvpn log for a 'Port pair' entry and return the public port."""
    try:
        if not os.path.exists(log_path):
            return 0
        text = Path(log_path).read_text().splitlines()
        for line in reversed(text):
            m = re.search(r"Port pair\s+(\d+)\s+(\d+)", line)
            if m:
                return int(m.group(1))
    except Exception as e:
        logging.error(f"Failed to parse log {log_path}: {e}")
    return 0


def _parse_port_from_qbittorrent_log() -> int:
    """Search qBittorrent's log for a port mapping line."""
    try:
        log_path = Path.home() / ".local" / "share" / "qBittorrent" / "logs" / "qbittorrent.log"
        if not log_path.is_file():
            return 0
        lines = log_path.read_text().splitlines()
        for line in reversed(lines):
            if "port" in line.lower():
                parts = [p for p in line.split() if p.isdigit()]
                if parts:
                    return int(parts[0])
    except Exception as e:
        logging.error(f"Failed to parse qBittorrent log: {e}")
    return 0

def start_forward(iface: str) -> int:
    """
    Initiate NAT-PMP mapping for the configured qBittorrent port,
    and spawn a background thread to refresh the mapping.
    Returns the first mapped public port (or 0 on error).
    """
    check_root()

    cfg = Config.load()
    internal_port = cfg.qb_port
    if not isinstance(internal_port, int) or internal_port <= 0:
        logging.error(f"Invalid qBittorrent port: {internal_port}")
        return 0

    try:
        gateway = _get_vpn_gateway(iface)
    except Exception:
        return 0

    pub_port = _request_mapping(gateway, internal_port)
    if not pub_port:
        # Attempt fallback by parsing pvpn.log for 'Port pair'
        log_path = os.path.join(cfg.config_dir, "pvpn.log")
        pub_port = _parse_port_from_log(log_path)
        if pub_port:
            logging.info(f"Recovered NAT-PMP port {pub_port} from logs")
    if not pub_port:
        pub_port = _parse_port_from_qbittorrent_log()
        if pub_port:
            logging.info(f"Recovered NAT-PMP port {pub_port} from qBittorrent logs")
    if not pub_port:
        logging.error("Initial NAT-PMP mapping failed")
        return 0

    logging.info(f"NAT-PMP mapping: public {pub_port} → internal {internal_port}")

    def _refresher():
        while True:
            time.sleep(REFRESH_INTERVAL)
            _request_mapping(gateway, internal_port)

    t = threading.Thread(target=_refresher, daemon=True)
    t.start()

    return pub_port


def get_public_port(iface: str, internal_port: int) -> int:
    """Query the current NAT-PMP mapping and return the public port."""
    try:
        gateway = _get_vpn_gateway(iface)
    except Exception:
        return 0
    return _request_mapping(gateway, internal_port)
