# pvpn/qbittorrent.py

"""
Manage qBittorrent-nox integration:
- update_port: set the listening port via WebUI API
- resume stalled torrents after restart
"""

import time
import logging
import requests

from pvpn.config import Config

# How long to wait before forcing a resume (seconds)
RESUME_TIMEOUT = 120
POLL_INTERVAL = 5

def update_port(cfg: Config, new_port: int):
    """
    Update qBittorrent's listen port to new_port via the WebUI API.
    If the WebUI is disabled, log a warning and skip the update.
    """
    if not cfg.qb_enable:
        logging.warning("qBittorrent WebUI disabled; skipping port update")
        return

    try:
        logging.info("Updating qBittorrent port via WebUI API")
        session = requests.Session()
        resp = session.post(
            f"{cfg.qb_url}/api/v2/auth/login",
            data={'username': cfg.qb_user, 'password': cfg.qb_pass},
            timeout=10,
        )
        resp.raise_for_status()

        prefs = {
            'listen_port': new_port,
            'random_port': False,
            'upnp': False,
        }
        r2 = session.post(
            f"{cfg.qb_url}/api/v2/app/setPreferences",
            json=prefs,
            timeout=10,
        )
        r2.raise_for_status()
        logging.info(f"WebUI API: listen_port set to {new_port}")
        _resume_torrents(cfg, session)
    except Exception as e:
        logging.error(f"WebUI API update failed: {e}")


def _resume_torrents(cfg: Config, session: requests.Session):
    """
    Wait up to RESUME_TIMEOUT; if no active downloads, send resumeAll via WebUI.
    """
    logging.info("Waiting to resume any stalled torrents")
    start = time.time()
    while time.time() - start < RESUME_TIMEOUT:
        time.sleep(POLL_INTERVAL)
        try:
            resp = session.get(f"{cfg.qb_url}/api/v2/torrents/info", timeout=10)
            resp.raise_for_status()
            torrents = resp.json()
            if any(t.get('state') in ('downloading', 'queued') for t in torrents):
                logging.info("Active torrents detected; not resuming")
                return
        except Exception as e:
            logging.debug(f"Error checking torrents: {e}")

    try:
        session.post(f"{cfg.qb_url}/api/v2/torrents/resumeAll", timeout=10).raise_for_status()
        logging.info("Sent resumeAll to qBittorrent WebUI")
    except Exception as e:
        logging.error(f"Failed to resume torrents: {e}")
