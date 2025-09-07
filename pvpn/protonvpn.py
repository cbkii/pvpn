# pvpn/protonvpn.py

"""Simplified connection management using local WireGuard configs.

This module no longer attempts to authenticate with the ProtonVPN API or
download configuration files. Instead it operates solely on WireGuard
configuration files that the user has placed in the configuration directory.
"""

import os
import sys
import logging

from pvpn.config import Config
from pvpn.utils import check_root

WG_DIR = "wireguard"


def connect(cfg: Config, args):
    """Bring up a WireGuard interface using an existing configuration."""

    check_root()
    wg_path = os.path.join(cfg.config_dir, WG_DIR)

    def _connect_with_conf(conf_file: str):
        from pvpn.wireguard import bring_up

        iface = bring_up(
            conf_file,
            dns=(args.dns == "true") if args.dns else cfg.network_dns_default,
        )

        if (args.ks == "true") or (args.ks is None and cfg.network_ks_default):
            from pvpn.routing import enable_killswitch

            enable_killswitch(iface)

        from pvpn.qbittorrent import start_service, update_port

        if cfg.qb_enable:
            start_service()

        from pvpn.natpmp import start_forward

        pub_port = start_forward(iface)

        if pub_port:
            update_port(cfg, pub_port)
        else:
            logging.warning("Port forwarding unavailable; continuing without it")

        from pvpn.monitor import start_monitor

        monitor_thread = start_monitor(cfg, iface)

        port_msg = pub_port if pub_port else "none"
        print(
            f"✅ Connected using {os.path.basename(conf_file)} on {iface}, forwarded port {port_msg}"
        )

        try:
            monitor_thread.join()
        except KeyboardInterrupt:
            pass

    if getattr(args, "config", None):
        conf_file = args.config
        if not os.path.isabs(conf_file):
            conf_file = os.path.join(wg_path, conf_file)
        if not os.path.isfile(conf_file):
            logging.error(f"WireGuard config {conf_file} not found")
            sys.exit(1)
        _connect_with_conf(conf_file)
        return

    if not os.path.isdir(wg_path):
        logging.error("WireGuard config directory missing")
        sys.exit(1)
    confs = [f for f in sorted(os.listdir(wg_path)) if f.endswith(".conf")]
    if not confs:
        logging.error("No WireGuard config files found")
        sys.exit(1)
    _connect_with_conf(os.path.join(wg_path, confs[0]))


def disconnect(cfg: Config, args):
    """Tear down the active WireGuard interface and optional kill-switch."""

    check_root()

    from pvpn.qbittorrent import stop_service

    if cfg.qb_enable:
        stop_service()

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

    RESET = "\033[0m"
    GREEN = "\033[92m"
    RED = "\033[91m"

    def line(label: str, ok: bool, value: str):
        icon = "✔" if ok else "✖"
        color = GREEN if ok else RED
        print(f"{color}{icon}{RESET} {label:<14}: {color}{value}{RESET}")

    iface = get_active_iface()
    line("Interface", bool(iface), iface if iface else "none")

    dns = get_dns_servers()
    line("DNS", bool(dns), ", ".join(dns) if dns else "unknown")

    ks = killswitch_status()
    line("Kill-switch", ks, "enabled" if ks else "disabled")

    pub_port = get_public_port(iface) if iface else 0
    line("Forwarded port", bool(pub_port), str(pub_port) if pub_port else "none")

    qb_port = get_listen_port(cfg)
    line("qBittorrent port", bool(qb_port), str(qb_port) if qb_port else "unknown")

