# pvpn/utils.py

"""
Utility functions for pvpn modules:
- run_cmd: execute shell commands safely
- backup_file / restore_file: file backup and restore operations
- check_root: ensure script runs with root privileges
"""

import subprocess
import logging
import shutil
import os
import sys

def run_cmd(cmd: str, capture_output: bool = True) -> str:
    """
    Run a shell command.
    Args:
        cmd: command string
        capture_output: if True, returns stdout; else runs live.
    Returns:
        stdout output if capture_output, else empty string.
    Raises:
        subprocess.CalledProcessError on non-zero exit.
    """
    logging.debug(f"Executing: {cmd}")
    if capture_output:
        result = subprocess.run(
            cmd, shell=True, check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        output = result.stdout.decode().strip()
        logging.debug(f"Output: {output}")
        return output
    else:
        subprocess.run(cmd, shell=True, check=True)
        return ""

def backup_file(src: str, dst: str):
    """
    Copy src to dst, overwriting dst if exists.
    Logs warnings on failure.
    """
    try:
        shutil.copy2(src, dst)
        logging.debug(f"Backed up {src} to {dst}")
    except Exception as e:
        logging.warning(f"Failed to backup {src} to {dst}: {e}")

def restore_file(src: str, dst: str):
    """
    Copy src to dst, restoring original file.
    """
    try:
        shutil.copy2(src, dst)
        logging.debug(f"Restored {src} to {dst}")
    except Exception as e:
        logging.warning(f"Failed to restore {src} to {dst}: {e}")

def check_root():
    """
    Exit if not running as root.
    """
    if os.geteuid() != 0:
        logging.error("Root privileges required. Please run as root or via sudo.")
        sys.exit(1)

