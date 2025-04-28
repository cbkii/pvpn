# pvpn/wireguard.py

"""
Manage WireGuard interface lifecycle:
- bring_up: create and configure the WireGuard interface from a .conf file
- bring_down: tear down any existing pvpn-managed WireGuard interfaces
- status: display interface and DNS status
"""

import os
import re
import logging
from pathlib import Path

from pvpn.utils import run_cmd, backup_file, restore_file, check_root

# Constants for DNS management
RESOLV_CONF = "/etc/resolv.conf"
RESOLV_BAK = "/etc/resolv.conf.pvpnbak"

def bring_up(conf_file: str, dns: bool = True) -> str:
    """
    Bring up a WireGuard interface using the given config file.
    - conf_file: path to .conf containing Address and optional DNS lines
    - dns: if True, back up and overwrite /etc/resolv.conf with config DNS
    Returns the interface name (e.g. 'wgpau123').
    """
    check_root()

    iface = Path(conf_file).stem
    addr = None
    dns_servers = []

    # Parse Address and DNS entries
    try:
        with open(conf_file, "r") as f:
            for line in f:
                m = re.match(r'#?\s*Address\s*=\s*(\S+)', line)
                if m:
                    addr = m.group(1)
                m2 = re.match(r'#?\s*DNS\s*=\s*(\S+)', line)
                if m2:
                    dns_servers.append(m2.group(1))
    except FileNotFoundError:
        logging.error(f"Config file not found: {conf_file}")
        raise
    except Exception as e:
        logging.error(f"Error reading {conf_file}: {e}")
        raise

    if not addr:
        raise ValueError(f"No Address found in {conf_file}")

    # Compute gateway (change last octet to .1)
    try:
        base = addr.split("/")[0].rsplit(".", 1)[0]
        gateway = f"{base}.1"
    except Exception as e:
        logging.error(f"Failed to parse gateway from Address '{addr}': {e}")
        raise

    # Backup DNS if requested
    if dns:
        backup_file(RESOLV_CONF, RESOLV_BAK)

    # Tear down stale interface if exists
    try:
        run_cmd(f"ip link del dev {iface}", capture_output=False)
    except Exception:
        pass  # ignore if not present

    # Create and configure interface
    run_cmd(f"ip link add dev {iface} type wireguard")
    run_cmd(f"wg setconf {iface} {conf_file}")
    run_cmd(f"ip address add {addr} peer {gateway} dev {iface}")
    run_cmd(f"ip link set up dev {iface}")
    logging.info(f"Brought up interface {iface} with IP {addr}")

    # Update DNS
    if dns and dns_servers:
        try:
            with open(RESOLV_CONF, "w") as r:
                r.write("# pvpn WireGuard DNS\n")
                for d in dns_servers:
                    r.write(f"nameserver {d}\n")
            logging.info(f"Updated {RESOLV_CONF} with ProtonDNS: {dns_servers}")
        except Exception as e:
            logging.error(f"Failed to write {RESOLV_CONF}: {e}")
            # Restore original DNS
            restore_file(RESOLV_BAK, RESOLV_CONF)

    return iface

def bring_down():
    """
    Tear down all WireGuard interfaces created by pvpn (matching wgp*).
    """
    check_root()

    try:
        output = run_cmd("ip -o link show")
    except Exception as e:
        logging.error(f"Failed to list interfaces: {e}")
        return

    for line in output.splitlines():
        m = re.search(r':\s*(wgp[a-z]{2}[0-9a-z]+):', line)
        if m:
            iface = m.group(1)
            try:
                run_cmd(f"ip link set down dev {iface}", capture_output=False)
                run_cmd(f"ip link del dev {iface}", capture_output=False)
                logging.info(f"Torn down WireGuard interface {iface}")
            except Exception as e:
                logging.error(f"Error tearing down {iface}: {e}")

def status():
    """
    Display status of pvpn-managed WireGuard interfaces and DNS.
    """
    try:
        print(run_cmd("wg show all"))
    except Exception as e:
        logging.error(f"wg show failed: {e}")
    try:
        print(run_cmd("ip -4 addr show | grep wgp"))
    except Exception:
        pass
    # Display current DNS
    try:
        print("DNS resolvers:")
        print(open(RESOLV_CONF).read())
    except Exception as e:
        logging.error(f"Failed to read {RESOLV_CONF}: {e}")
