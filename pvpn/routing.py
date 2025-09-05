# pvpn/routing.py

"""
Manage routing controls:
- iptables-based kill-switch
"""

import os
import logging
import subprocess

from pvpn.utils import run_cmd, check_root

def enable_killswitch(iface: str):
    """
    Enable a strict iptables kill-switch:
      - backup current rules
      - DROP all OUTPUT except on VPN interface and loopback
    """
    check_root()
    bak = "/etc/pvpn-iptables.bak"
    try:
        result = subprocess.run(["iptables-save"], check=True, stdout=subprocess.PIPE)
        with open(bak, "w") as f:
            f.write(result.stdout.decode())
        run_cmd(["iptables", "-P", "OUTPUT", "DROP"], capture_output=False)
        run_cmd(["iptables", "-A", "OUTPUT", "-o", iface, "-j", "ACCEPT"], capture_output=False)
        run_cmd(["iptables", "-A", "OUTPUT", "-o", "lo", "-j", "ACCEPT"], capture_output=False)
        run_cmd([
            "iptables", "-A", "OUTPUT", "-m", "conntrack",
            "--ctstate", "ESTABLISHED,RELATED", "-j", "ACCEPT",
        ], capture_output=False)
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
            with open(bak) as f:
                run_cmd(["iptables-restore"], capture_output=False, input_text=f.read())
            logging.info("Kill-switch disabled, iptables restored")
        except Exception as e:
            logging.error(f"Failed to restore iptables: {e}")
    else:
        logging.warning("No iptables backup found; cannot disable kill-switch")


def killswitch_status() -> bool:
    """Return True if the kill-switch appears active."""
    try:
        rules = run_cmd(["iptables", "-S", "OUTPUT"])
        if "-P OUTPUT DROP" in rules and os.path.exists("/etc/pvpn-iptables.bak"):
            return True
    except Exception as e:
        logging.error(f"Failed to check kill-switch: {e}")
    return False

