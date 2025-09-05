# pvpn/utils.py

"""
Utility functions for pvpn modules:
- run_cmd: execute commands without invoking a shell
- backup_file / restore_file: file backup and restore operations
- check_root: ensure script runs with root privileges
"""

import subprocess
import logging
import shutil
import os
import sys
import shlex
from typing import Sequence, Union

def run_cmd(cmd: Union[str, Sequence[str]], *, capture_output: bool = True, input_text: str | None = None) -> str:
    """Run a command without using the shell.

    Args:
        cmd: command string or sequence of arguments.
        capture_output: if True, returns stdout; else streams to caller.
        input_text: optional text passed to stdin.

    Returns:
        stdout output if ``capture_output`` else an empty string.

    Raises:
        ``subprocess.CalledProcessError`` on non-zero exit.
    """
    if isinstance(cmd, str):
        cmd_list = shlex.split(cmd)
    else:
        cmd_list = list(cmd)
    logging.debug(f"Executing: {' '.join(cmd_list)}")
    result = subprocess.run(
        cmd_list,
        check=True,
        stdout=subprocess.PIPE if capture_output else None,
        stderr=subprocess.PIPE if capture_output else None,
        input=input_text.encode() if input_text else None,
    )
    if capture_output:
        output = result.stdout.decode().strip()
        logging.debug(f"Output: {output}")
        return output
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

