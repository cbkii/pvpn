# pvpn/routing.py

"""
Manage routing controls:
- iptables-based kill-switch
- split-tunnel via iptables mangle + policy routing
- CLI handler for tunnel rules
"""

import os
import logging
import json
import subprocess

from pvpn.utils import run_cmd, check_root

# Constants
SPLIT_CHAIN = "PVPN_SPLIT"
MARK = "0x1"
TABLE_ID = "100"  # custom routing table for split-tunnel

def enable_killswitch(iface: str):
    """
    Enable a strict iptables kill-switch:
      - backup current rules
      - DROP all OUTPUT except on VPN interface and loopback
    """
    check_root()
    bak = "/etc/pvpn-iptables.bak"
    try:
        run_cmd(f"iptables-save > {bak}", capture_output=False)
        run_cmd("iptables -P OUTPUT DROP", capture_output=False)
        run_cmd(f"iptables -A OUTPUT -o {iface} -j ACCEPT", capture_output=False)
        run_cmd("iptables -A OUTPUT -o lo -j ACCEPT", capture_output=False)
        logging.info("Kill-switch enabled")
    except Exception as e:
        logging.error(f"Failed to enable kill-switch: {e}")

def disable_killswitch():
    """
    Disable the kill-switch by restoring iptables from backup.
    """
    check_root()
    bak = "/etc/pvpn-iptables.bak"
    if os.path.exists(bak):
        try:
            run_cmd(f"iptables-restore < {bak}", capture_output=False)
            logging.info("Kill-switch disabled, iptables restored")
        except Exception as e:
            logging.error(f"Failed to restore iptables: {e}")
    else:
        logging.warning("No iptables backup found; cannot disable kill-switch")

def _ensure_chain():
    """
    Ensure the custom mangle chain exists and is hooked into OUTPUT.
    """
    # Create chain if missing
    try:
        run_cmd(f"iptables -t mangle -N {SPLIT_CHAIN}", capture_output=False)
    except Exception:
        pass
    # Hook into OUTPUT
    try:
        run_cmd(f"iptables -t mangle -C OUTPUT -j {SPLIT_CHAIN}", capture_output=False)
    except Exception:
        try:
            run_cmd(f"iptables -t mangle -A OUTPUT -j {SPLIT_CHAIN}", capture_output=False)
        except Exception as e:
            logging.error(f"Failed to hook {SPLIT_CHAIN} into OUTPUT: {e}")

def clear_split_rules():
    """
    Flush mangle chain and remove policy routing for split-tunnel.
    """
    check_root()
    try:
        run_cmd(f"iptables -t mangle -F {SPLIT_CHAIN}", capture_output=False)
    except Exception as e:
        logging.error(f"Failed to flush {SPLIT_CHAIN}: {e}")
    # Remove ip rule and route
    try:
        run_cmd(f"ip rule del fwmark {MARK} table {TABLE_ID}", capture_output=False)
    except Exception:
        pass
    try:
        run_cmd(f"ip route del default table {TABLE_ID}", capture_output=False)
    except Exception:
        pass
    logging.info("Split-tunnel rules cleared")

def apply_split_tunnel(cfg):
    """
    Apply split-tunnel rules from tunnel.json:
      - mark packets for listed processes, PIDs, or IPs
      - add policy routing for marked packets
    """
    check_root()
    _ensure_chain()
    clear_split_rules()

    # Load rules
    try:
        with open(cfg.tunnel_json_path) as f:
            rules = json.load(f)
    except Exception as e:
        logging.error(f"Failed to load split-tunnel rules: {e}")
        rules = {}

    # Mark by process name
    for proc in rules.get("processes", []):
        try:
            run_cmd(
                f"iptables -t mangle -A {SPLIT_CHAIN} "
                f"-m string --string \"{proc}\" --algo bm "
                f"-j MARK --set-mark {MARK}",
                capture_output=False
            )
        except Exception as e:
            logging.error(f"Failed to mark process '{proc}': {e}")

    # Mark by PID
    for pid in rules.get("pids", []):
        try:
            run_cmd(
                f"iptables -t mangle -A {SPLIT_CHAIN} "
                f"-m owner --pid-owner {pid} "
                f"-j MARK --set-mark {MARK}",
                capture_output=False
            )
        except Exception as e:
            logging.error(f"Failed to mark PID '{pid}': {e}")

    # Mark by IP
    for ip in rules.get("ips", []):
        try:
            run_cmd(
                f"iptables -t mangle -A {SPLIT_CHAIN} "
                f"-d {ip} -j MARK --set-mark {MARK}",
                capture_output=False
            )
        except Exception as e:
            logging.error(f"Failed to mark IP '{ip}': {e}")

    # Determine main gateway and interface
    try:
        parts = run_cmd("ip route show default").split()
        gw = parts[parts.index("via") + 1]
        iface = parts[parts.index("dev") + 1]
    except Exception as e:
        logging.error(f"Failed to get default route: {e}")
        return

    # Add policy routing
    try:
        run_cmd(f"ip rule add fwmark {MARK} table {TABLE_ID}", capture_output=False)
        run_cmd(f"ip route add default via {gw} dev {iface} table {TABLE_ID}", capture_output=False)
        logging.info(f"Split-tunnel applied: {rules}")
    except Exception as e:
        logging.error(f"Failed to add policy routing: {e}")

def manage_tunnel(cfg, args):
    """
    Handler for `pvpn tunnel` CLI:
      --add/--rm with exactly one of --process, --pid, or --ip
      --edit to open tunnel.json
    """
    if args.edit:
        editor = os.getenv("EDITOR", "vi")
        os.system(f"{editor} {cfg.tunnel_json_path}")
        return

    rules = cfg.load_tunnel_rules()
    key, val = None, None
    if args.process:
        key, val = "processes", args.process
    elif args.pid is not None:
        key, val = "pids", str(args.pid)
    elif args.ip:
        key, val = "ips", args.ip
    else:
        logging.error("Please specify --process, --pid, or --ip")
        return

    lst = rules.get(key, [])
    if args.add:
        if val not in lst:
            lst.append(val)
            logging.info(f"Added {val} to {key}")
    elif args.rm:
        if val in lst:
            lst.remove(val)
            logging.info(f"Removed {val} from {key}")

    rules[key] = lst
    cfg.save_tunnel_rules(rules)
    print(json.dumps(rules, indent=2))
