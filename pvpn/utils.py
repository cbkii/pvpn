# pvpn/utils.py

"""
Utility functions for pvpn modules:
- run_cmd: execute shell commands safely
- backup_file / restore_file: file backup and restore operations
- check_root: ensure script runs with root privileges
- get_invoker_home: resolve the real user's home directory even when run
  via sudo
- chown_to_invoker: ensure files/directories created under sudo remain
  owned by the invoking user
"""

import subprocess
import logging
import shutil
import os
import sys
from pathlib import Path
import pwd

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


def get_invoker_home() -> Path:
    """Return the home directory of the user invoking pvpn.

    pvpn commands generally require root via ``sudo``.  Using
    :func:`Path.home` in such cases resolves to ``/root`` which causes
    configuration files to be written to the wrong location.  This helper
    returns the original user's home directory when run under ``sudo`` so
    that configuration is consistently stored in the invoking user's
    environment.

    Returns:
        Path: Path object pointing to the preferred home directory.
    """

    home = Path.home()
    if os.geteuid() == 0 and os.environ.get("SUDO_USER"):
        try:
            home = Path(pwd.getpwnam(os.environ["SUDO_USER"]).pw_dir)
        except KeyError:
            # Fall back to root's home if lookup fails
            pass
    return home


def chown_to_invoker(path: Path | str):
    """Ensure *path* is owned by the user invoking pvpn.

    When pvpn runs under ``sudo``, files created in the invoking user's
    home would otherwise be owned by root.  This helper uses ``SUDO_UID``
    and ``SUDO_GID`` to restore ownership so that subsequent non-root
    processes (e.g. qbittorrent) can access them.

    The function is a no-op if not running as root or if the sudo
    environment variables are absent.
    """

    if os.geteuid() != 0:
        return

    uid = os.environ.get("SUDO_UID")
    gid = os.environ.get("SUDO_GID")
    if not uid or not gid:
        return

    try:
        os.chown(str(path), int(uid), int(gid))
    except Exception as e:
        logging.debug(f"Failed to chown {path} to invoking user: {e}")

