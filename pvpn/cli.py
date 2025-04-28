#!/usr/bin/env python3
# pvpn/cli.py

import argparse
import sys
import shutil
from pvpn.config import Config
from pvpn import protonvpn, routing, wireguard, natpmp, qbittorrent

def check_dependencies():
    """
    Warn if required system tools are missing.
    """
    required = ["wg", "ip", "iptables", "natpmpc", "ping", "curl", "jq"]
    missing = [tool for tool in required if shutil.which(tool) is None]
    if missing:
        print(f"Warning: Missing system tools: {', '.join(missing)}. Some features may not work.")

def build_parser():
    p = argparse.ArgumentParser(
        prog="pvpn",
        description="Headless ProtonVPN WireGuard CLI with qBittorrent-nox integration"
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    # init
    init = sub.add_parser("init", help="Interactive setup or configure components")
    init.add_argument("--proton", action="store_true", help="Configure ProtonVPN credentials/settings")
    init.add_argument("--qb", action="store_true", help="Configure qBittorrent-WebUI settings")
    init.add_argument("--tunnel", action="store_true", help="Configure split-tunnel defaults")
    init.add_argument("--network", action="store_true", help="Configure DNS & kill-switch defaults")
    init.set_defaults(cmd="init")

    # connect
    conn = sub.add_parser("connect", aliases=["c"], help="Establish VPN connection")
    conn.set_defaults(cmd="connect")
    conn.add_argument("-c", "--cc", metavar="COUNTRY", help="Country code (e.g. AU)")
    conn.add_argument("--sc", action="store_true", help="Use SecureCore servers")
    conn.add_argument("--p2p", action="store_true", help="Use P2P servers")
    conn.add_argument("-f", "--fastest", choices=["ping", "api"], default=None,
                      help="Server selection method")
    conn.add_argument("-t", "--threshold", type=int, metavar="1-100", default=None,
                      help="Maximum server load percentage")
    conn.add_argument("-l", "--latency-cutoff", type=int, metavar="MS", default=None,
                      help="Return first server with ping < cutoff ms")
    conn.add_argument("--dns", choices=["true", "false"], default=None,
                      help="Switch to ProtonDNS (true|false)")
    conn.add_argument("--ks", choices=["true", "false"], default=None,
                      help="Enable kill-switch (true|false)")

    # disconnect
    disc = sub.add_parser("disconnect", aliases=["d"], help="Tear down VPN connection")
    disc.set_defaults(cmd="disconnect")
    disc.add_argument("--ks", choices=["true", "false"], default=None,
                      help="Leave kill-switch active? (true|false)")

    # status
    stat = sub.add_parser("status", aliases=["s"], help="Show VPN & qBittorrent status")
    stat.set_defaults(cmd="status")

    # list
    lst = sub.add_parser("list", help="List available servers")
    lst.set_defaults(cmd="list")
    lst.add_argument("-c", "--cc", help="Country code filter")
    lst.add_argument("--sc", action="store_true", help="SecureCore only")
    lst.add_argument("--p2p", action="store_true", help="P2P only")
    lst.add_argument("-f", "--fastest", choices=["ping", "api"], default=None,
                     help="Sort by latency/load")
    lst.add_argument("-t", "--threshold", type=int,
                     help="Maximum server load percentage")

    # tunnel
    tnl = sub.add_parser("tunnel", help="Manage split-tunnel rules")
    tnl.set_defaults(cmd="tunnel")
    grp = tnl.add_mutually_exclusive_group(required=True)
    grp.add_argument("--add", action="store_true")
    grp.add_argument("--rm", action="store_true")
    tnl.add_argument("--process", help="Binary name to tunnel")
    tnl.add_argument("--pid", type=int, help="PID to tunnel")
    tnl.add_argument("--ip", help="IP or CIDR to tunnel")
    tnl.add_argument("--edit", action="store_true",
                     help="Edit split-tunnel JSON manually")

    return p

def main():
    check_dependencies()
    parser = build_parser()
    args = parser.parse_args()
    cfg = Config.load()

    cmd = args.cmd
    if cmd == "init":
        cfg.interactive_setup(
            proton=args.proton,
            qb=args.qb,
            tunnel=args.tunnel,
            network=args.network
        )

    elif cmd == "connect":
        protonvpn.connect(cfg, args)

    elif cmd == "disconnect":
        protonvpn.disconnect(cfg, args)

    elif cmd == "status":
        protonvpn.status(cfg)

    elif cmd == "list":
        protonvpn.list_servers(cfg, args)

    elif cmd == "tunnel":
        routing.manage_tunnel(cfg, args)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
