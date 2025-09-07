#!/usr/bin/env python3
# pvpn/cli.py

import argparse
import sys
import shutil
import logging
from pvpn.config import Config
from pvpn import protonvpn


def check_dependencies():
    """Warn if required system tools are missing."""
    required = ["wg", "ip", "iptables", "natpmpc", "ping", "curl"]
    missing = [tool for tool in required if shutil.which(tool) is None]
    if missing:
        print(f"Warning: Missing system tools: {', '.join(missing)}. Some features may not work.")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pvpn",
        description="Headless ProtonVPN WireGuard CLI with qBittorrent-nox integration",
    )
    p.add_argument(
        "--log-level",
        choices=["debug", "info", "warning", "error"],
        default="info",
        help="Logging verbosity",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    # init
    init = sub.add_parser("init", help="Interactive setup or configure components")
    init.add_argument("--proton", action="store_true", help="Configure ProtonVPN credentials/settings")
    init.add_argument("--qb", action="store_true", help="Configure qBittorrent-WebUI settings")
    init.add_argument("--network", action="store_true", help="Configure DNS & kill-switch defaults")
    init.set_defaults(cmd="init")

    # connect
    conn = sub.add_parser("connect", aliases=["c"], help="Establish VPN connection")
    conn.set_defaults(cmd="connect")
    conn.add_argument("--config", help="Path to WireGuard .conf file")
    conn.add_argument("--dns", choices=["true", "false"], default=None, help="Switch DNS (true|false)")
    conn.add_argument("--ks", choices=["true", "false"], default=None, help="Enable kill-switch (true|false)")

    # disconnect
    disc = sub.add_parser("disconnect", aliases=["d"], help="Tear down VPN connection")
    disc.set_defaults(cmd="disconnect")
    disc.add_argument("--ks", choices=["true", "false"], default=None, help="Leave kill-switch active? (true|false)")

    # status
    stat = sub.add_parser("status", aliases=["s"], help="Show VPN & qBittorrent status")
    stat.set_defaults(cmd="status")

    return p


def main() -> None:
    check_dependencies()
    parser = build_parser()
    args = parser.parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s %(levelname)s: %(message)s",
    )
    cfg = Config.load()

    cmd = args.cmd
    if cmd == "init":
        cfg.interactive_setup(proton=args.proton, qb=args.qb, network=args.network)
    elif cmd == "connect":
        protonvpn.connect(cfg, args)
    elif cmd == "disconnect":
        protonvpn.disconnect(cfg, args)
    elif cmd == "status":
        protonvpn.status(cfg)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    main()
