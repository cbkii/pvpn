# pvpn/monitor.py

"""Background connection monitoring for pvpn.

This module spawns a daemon thread that periodically pings the current
WireGuard peer. If the ping fails or exceeds a latency threshold a number
of consecutive times, the VPN connection is cycled by invoking
``protonvpn.disconnect`` followed by ``protonvpn.connect``.

Configuration is sourced from :class:`pvpn.config.Config` via the following
fields (with defaults shown)::

    monitor_interval = 60           # seconds between checks
    monitor_failures = 3            # consecutive bad pings before reconnect
    monitor_latency_threshold = 500 # milliseconds considered too slow

"""

from __future__ import annotations

import logging
import subprocess
import threading
import time
from types import SimpleNamespace

from pvpn.config import Config
from pvpn import protonvpn


def _get_endpoint_ip(iface: str) -> str | None:
    """Return the endpoint IP for the first peer on ``iface``.

    Uses ``wg show <iface> endpoints`` and parses the first line to obtain the
    peer IP. Returns ``None`` if it cannot be determined.
    """

    try:
        out = subprocess.check_output(
            ["wg", "show", iface, "endpoints"], text=True, timeout=5
        ).strip()
        if not out:
            return None
        parts = out.split()
        if len(parts) >= 2:
            return parts[1].split(":")[0]
    except Exception as exc:  # noqa: BLE001
        logging.debug(f"monitor: failed to get endpoint for {iface}: {exc}")
    return None


def _ping(ip: str) -> float | None:
    """Ping ``ip`` once and return the average RTT in ms.

    Returns ``None`` on timeout or other error.
    """

    try:
        out = subprocess.check_output(
            ["ping", "-c", "1", "-W", "2", ip],
            stderr=subprocess.DEVNULL,
            timeout=5,
            text=True,
        )
        stats = next((l for l in out.splitlines() if "rtt min/avg" in l), "")
        return float(stats.split("/")[4]) if stats else None
    except Exception:  # noqa: BLE001
        return None


def _monitor_loop(cfg: Config, iface: str) -> None:
    """Worker loop run in a background thread."""

    interval = cfg.monitor_interval
    failure_limit = cfg.monitor_failures
    latency_limit = cfg.monitor_latency_threshold
    failures = 0

    logging.info(
        "Starting monitor on %s (interval=%ss, failures=%s, latency=%sms)",
        iface,
        interval,
        failure_limit,
        latency_limit,
    )

    while True:
        time.sleep(interval)
        ip = _get_endpoint_ip(iface)
        if not ip:
            logging.warning("monitor: could not determine peer endpoint")
            failures += 1
        else:
            latency = _ping(ip)
            if latency is None or latency > latency_limit:
                logging.warning(
                    "monitor: ping failed or high latency (%s ms) to %s", latency, ip
                )
                failures += 1
            else:
                logging.debug("monitor: latency %sms to %s", latency, ip)
                failures = 0

        if failures >= failure_limit:
            logging.warning("monitor: threshold reached, rotating server")
            # minimal args for disconnect/connect
            disc_args = SimpleNamespace(ks=None)
            conn_args = SimpleNamespace(
                cc=None,
                sc=False,
                p2p=False,
                threshold=None,
                fastest=None,
                latency_cutoff=None,
                dns=None,
                ks=None,
            )
            try:
                protonvpn.disconnect(cfg, disc_args)
            except Exception as exc:  # noqa: BLE001
                logging.error(f"monitor: disconnect failed: {exc}")
            try:
                protonvpn.connect(cfg, conn_args)
            except Exception as exc:  # noqa: BLE001
                logging.error(f"monitor: reconnect failed: {exc}")
            return


def start_monitor(cfg: Config, iface: str) -> threading.Thread:
    """Spawn the monitoring thread and return it."""

    thread = threading.Thread(target=_monitor_loop, args=(cfg, iface))
    thread.start()
    return thread


__all__ = ["start_monitor"]

