# pvpn/qbittorrent.py

"""
Manage qBittorrent-nox integration:
- update_port: set the listening port via WebUI API or config file fallback
- resume stalled torrents after restart
"""

import time
import logging
import requests
import subprocess
from pathlib import Path

from pvpn.config import Config
from pvpn.utils import run_cmd, check_root

# How long to wait before forcing a resume (seconds)
RESUME_TIMEOUT = 120
POLL_INTERVAL = 5

def update_port(cfg: Config, new_port: int):
    """
    Update qBittorrent's listen port to new_port:
      1) Attempt via WebUI API
      2) Fallback to direct config-file edit
      3) Resume torrents if none active after restart
    """
    if cfg.qb_enable:
        try:
            logging.info("Updating qBittorrent port via WebUI API")
            session = requests.Session()
            # Login
            resp = session.post(
                f"{cfg.qb_url}/api/v2/auth/login",
                data={'username': cfg.qb_user, 'password': cfg.qb_pass},
                timeout=10
            )
            resp.raise_for_status()

            # Set preferences
            prefs = {
                'listen_port': new_port,
                'Connection\\RandomPort': False,
                'Connection\\UPnPNAT': False
            }
            r2 = session.post(
                f"{cfg.qb_url}/api/v2/app/setPreferences",
                json=prefs,
                timeout=10
            )
            r2.raise_for_status()
            logging.info(f"WebUI API: listen_port set to {new_port}")
        except Exception as e:
            logging.warning(f"WebUI API update failed: {e}")
            _config_file_update(new_port)
    else:
        _config_file_update(new_port)

    _resume_torrents(cfg)

def _config_file_update(new_port: int):
    """
    Stop qbittorrent-nox, edit qBittorrent.conf, restart service.
    """
    logging.info("Updating qBittorrent via config-file fallback")
    check_root()

    # Stop the service
    try:
        run_cmd("systemctl stop qbittorrent-nox", capture_output=False)
    except Exception as e:
        logging.warning(f"Could not stop qbittorrent-nox: {e}")

    # Edit the config file
    conf_path = Path.home() / ".config" / "qBittorrent" / "qBittorrent.conf"
    if not conf_path.is_file():
        logging.error(f"qBittorrent config not found: {conf_path}")
    else:
        try:
            lines = conf_path.read_text().splitlines()
            out = []
            for line in lines:
                if line.startswith("Connection\\Port="):
                    out.append(f"Connection\\Port={new_port}")
                else:
                    out.append(line)
            conf_path.write_text("\n".join(out))
            logging.info(f"Set Connection\\Port={new_port} in {conf_path}")
        except Exception as e:
            logging.error(f"Failed to edit {conf_path}: {e}")

    # Restart the service
    try:
        run_cmd("systemctl start qbittorrent-nox", capture_output=False)
    except Exception as e:
        logging.warning(f"Could not start qbittorrent-nox: {e}")

def _resume_torrents(cfg: Config):
    """
    Wait up to RESUME_TIMEOUT; if no active downloads, send resumeAll via WebUI.
    """
    logging.info("Waiting to resume any stalled torrents")
    start = time.time()
    while time.time() - start < RESUME_TIMEOUT:
        time.sleep(POLL_INTERVAL)
        try:
            session = requests.Session()
            resp = session.get(f"{cfg.qb_url}/api/v2/torrents/info", timeout=10)
            resp.raise_for_status()
            torrents = resp.json()
            # If any downloading or queued, skip resume
            if any(t.get('state') in ('downloading', 'queued') for t in torrents):
                logging.info("Active torrents detected; not resuming")
                return
        except Exception as e:
            logging.debug(f"Error checking torrents: {e}")

    # No active downloads; resume all
    try:
        session = requests.Session()
        session.post(f"{cfg.qb_url}/api/v2/torrents/resumeAll", timeout=10)
        logging.info("Sent resumeAll to qBittorrent WebUI")
    except Exception as e:
        logging.error(f"Failed to resume torrents: {e}")


def get_listen_port(cfg: Config) -> int:
    """Retrieve the current qBittorrent listening port."""
    if cfg.qb_enable:
        try:
            session = requests.Session()
            resp = session.post(
                f"{cfg.qb_url}/api/v2/auth/login",
                data={'username': cfg.qb_user, 'password': cfg.qb_pass},
                timeout=10,
            )
            resp.raise_for_status()
            pref = session.get(f"{cfg.qb_url}/api/v2/app/preferences", timeout=10)
            pref.raise_for_status()
            data = pref.json()
            port = data.get('listen_port')
            if isinstance(port, int) and port > 0:
                return port
        except Exception as e:
            logging.warning(f"WebUI API query failed: {e}")
    conf_path = Path.home() / ".config" / "qBittorrent" / "qBittorrent.conf"
    try:
        for line in conf_path.read_text().splitlines():
            if line.startswith("Connection\\Port="):
                return int(line.split("=", 1)[1])
    except Exception as e:
        logging.debug(f"Failed to read qBittorrent config: {e}")
    return cfg.qb_port
