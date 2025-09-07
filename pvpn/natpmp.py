# pvpn/natpmp.py

"""
Handle NAT-PMP port forwarding via `natpmpc` for a given WireGuard interface.
Requests a mapping from the VPN gateway to the local qBittorrent port,
then periodically refreshes the lease.
"""

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
        out = run_cmd(["ip", "route", "show", "dev", iface])
        for line in out.splitlines():
            if line.startswith("default"):
                parts = line.split()
                return parts[parts.index("via") + 1]
        raise RuntimeError("no default route found")
    except Exception as e:
        logging.error(f"Failed to get VPN gateway for interface {iface}: {e}")
        raise

def _request_mapping(gateway: str) -> int:
    """
    Request a NAT-PMP port mapping from the given gateway using ``natpmpc``.

    ProtonVPN assigns the public port automatically; we request a placeholder
    mapping (internal port ``1`` and external ``0``) for both UDP and TCP and
    return the chosen public port. On any failure, return ``0``.
    """
    port = 0
    for proto in ("udp", "tcp"):
        cmd = ["natpmpc", "-a", "1", "0", proto, "60", "-g", gateway]
        try:
            out = subprocess.check_output(
                cmd, stderr=subprocess.STDOUT, timeout=10
            ).decode()
            for line in out.splitlines():
                if "Mapped public port" in line:
                    port = int(line.strip().split()[3])
                    break
            if not port:
                logging.error(f"No mapping found in natpmpc output:\n{out}")
        except subprocess.TimeoutExpired:
            logging.error("natpmpc request timed out")
        except subprocess.CalledProcessError as e:
            logging.error(f"natpmpc failed: {e.output.decode().strip()}")
        except Exception as e:
            logging.error(f"Unexpected error calling natpmpc: {e}")
    return port


def probe_server(ip: str) -> bool:
    """Return ``True`` if the server responds to a NAT-PMP mapping request."""
    return _request_mapping(ip) != 0

def start_forward(iface: str) -> int:
    """
    Initiate NAT-PMP mapping for the configured qBittorrent port,
    and spawn a background thread to refresh the mapping.
    Returns the first mapped public port (or 0 on error).
    """
    check_root()

    try:
        gateway = _get_vpn_gateway(iface)
    except Exception:
        return 0

    pub_port = _request_mapping(gateway)
    if not pub_port:
        logging.warning("Initial NAT-PMP mapping failed")
        return 0

    cfg = Config.load()
    logging.info(f"NAT-PMP mapping obtained public port {pub_port}")
    cfg.qb_port = pub_port

    def _refresher():
        current = pub_port
        while True:
            time.sleep(REFRESH_INTERVAL)
            new_port = _request_mapping(gateway)
            if new_port and new_port != current:
                logging.info(f"NAT-PMP port changed {current} -> {new_port}")
                try:
                    from pvpn.qbittorrent import update_port
                    update_port(cfg, new_port)
                    cfg.qb_port = new_port
                except Exception as e:
                    logging.error(f"Failed to update qBittorrent: {e}")
                current = new_port

    t = threading.Thread(target=_refresher, daemon=True)
    t.start()

    return pub_port


def get_public_port(iface: str) -> int:
    """Query the current NAT-PMP mapping and return the public port."""
    try:
        gateway = _get_vpn_gateway(iface)
    except Exception:
        return 0
    return _request_mapping(gateway)
