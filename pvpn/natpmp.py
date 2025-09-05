# pvpn/natpmp.py

"""
Handle NAT-PMP port forwarding via `natpmpc` for a given WireGuard interface.
Requests a mapping from the VPN gateway to the local qBittorrent port,
then periodically refreshes the lease.
"""

import os
import subprocess
import threading
import time
import logging

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
        logging.warning("Initial NAT-PMP mapping failed")
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
