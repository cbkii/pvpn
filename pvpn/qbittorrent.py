# pvpn/qbittorrent.py

"""
Manage qBittorrent-nox integration:
- update_port: set the listening port via WebUI API
- get_listen_port: determine qBittorrent's current listen port
- resume stalled torrents after restart
"""

import time
import logging
import requests
import configparser
import subprocess
from pathlib import Path

from pvpn.config import Config
from pvpn.utils import run_cmd

# How long to wait before forcing a resume (seconds)
RESUME_TIMEOUT = 120
POLL_INTERVAL = 5


def config_path() -> Path:
    """Return the path to qBittorrent's configuration file.

    Preference order:
    1. ``~/qbprofile/qBittorrent/config/qBittorrent.conf``
    2. ``--profile`` path from a running ``qbittorrent-nox`` process
    3. Legacy ``~/.config/qBittorrent/qBittorrent.conf``
    """

    default = (
        Path.home()
        / "qbprofile"
        / "qBittorrent"
        / "config"
        / "qBittorrent.conf"
    )
    if default.exists():
        return default

    try:
        out = subprocess.check_output(
            ["pgrep", "-a", "qbittorrent-nox"],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        for line in out.splitlines():
            parts = line.split()
            for i, part in enumerate(parts):
                profile = None
                if part.startswith("--profile="):
                    profile = part.split("=", 1)[1]
                elif part == "--profile" and i + 1 < len(parts):
                    profile = parts[i + 1]
                if profile:
                    conf = (
                        Path(profile)
                        / "qBittorrent"
                        / "config"
                        / "qBittorrent.conf"
                    )
                    if conf.exists():
                        return conf
    except Exception as e:  # pragma: no cover - best-effort
        logging.debug(f"Failed to detect qbittorrent profile: {e}")

    return Path.home() / ".config" / "qBittorrent" / "qBittorrent.conf"

def update_port(cfg: Config, new_port: int):
    """
    Update qBittorrent's listen port to ``new_port`` via the WebUI API.
    If the WebUI is disabled or ``new_port`` is falsy, skip the update.
    """
    if not cfg.qb_enable:
        logging.warning("qBittorrent WebUI disabled; skipping port update")
        return

    if not new_port or new_port <= 0:
        logging.warning("No forwarded port provided; skipping qBittorrent update")
        return

    session = requests.Session()
    try:
        logging.info("Updating qBittorrent port via WebUI API")
        resp = session.post(
            f"{cfg.qb_url}/api/v2/auth/login",
            data={"username": cfg.qb_user, "password": cfg.qb_pass},
            timeout=10,
        )
        resp.raise_for_status()
        if resp.text.strip() != "Ok.":
            logging.error("qBittorrent WebUI login failed")
            return

        prefs = {
            "listen_port": new_port,
            "random_port": False,
            "upnp": False,
            "use_natpmp": False,
        }
        r2 = session.post(
            f"{cfg.qb_url}/api/v2/app/setPreferences",
            json=prefs,
            timeout=10,
        )
        r2.raise_for_status()
        logging.info(f"WebUI API: listen_port set to {new_port}")
        _resume_torrents(cfg, session)
    except requests.RequestException as e:
        logging.error(f"WebUI API update failed: {e}")
    finally:
        close = getattr(session, "close", None)
        if close:
            close()


def get_listen_port(cfg: Config) -> int:
    """Return qBittorrent's current listening port.

    Tries up to three methods before falling back to the configured port:

    1. WebUI API (if enabled)
    2. Parsing qBittorrent's configuration file
    3. Inspecting open sockets via ``ss``
    """

    # 1. WebUI API
    if cfg.qb_enable:
        session = requests.Session()
        try:
            session.post(
                f"{cfg.qb_url}/api/v2/auth/login",
                data={'username': cfg.qb_user, 'password': cfg.qb_pass},
                timeout=5,
            ).raise_for_status()
            resp = session.get(f"{cfg.qb_url}/api/v2/app/preferences", timeout=5)
            resp.raise_for_status()
            port = int(resp.json().get('listen_port') or 0)
            if port:
                return port
        except requests.RequestException as e:
            logging.debug(f"WebUI API port query failed: {e}")
        finally:
            close = getattr(session, "close", None)
            if close:
                close()

    # 2. Config file
    try:
        cfg_file = config_path()
        parser = configparser.RawConfigParser()
        parser.optionxform = lambda opt: opt  # type: ignore[assignment]
        parser.read(cfg_file)
        if 'Preferences' in parser:
            pref = parser['Preferences']
            for key in (
                'Session\\Port',
                'Connection\\PortRangeMin',
                'Bittorrent\\PortRangeMin',
            ):
                if key in pref:
                    port = int(pref[key])
                    if port:
                        return port
    except Exception as e:
        logging.debug(f"Config file port query failed: {e}")

    # 3. ``ss`` output
    try:
        out = subprocess.check_output(
            ["ss", "-ltnp"], stderr=subprocess.DEVNULL, timeout=5
        ).decode()
        for line in out.splitlines():
            if "qbittorrent-nox" in line:
                try:
                    local = line.split()[3]
                    port = int(local.rsplit(":", 1)[1])
                    if port:
                        return port
                except Exception:
                    continue
    except Exception as e:
        logging.debug(f"Socket inspection failed: {e}")

    logging.warning("Unable to determine qBittorrent listen port; using configured port")
    return cfg.qb_port


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


def start_service():
    """Start the qbittorrent-nox systemd service."""
    try:
        run_cmd(["systemctl", "start", "qbittorrent-nox"], capture_output=False)
        logging.info("Started qbittorrent-nox service")
    except Exception as e:
        logging.error(f"Failed to start qbittorrent-nox: {e}")


def stop_service():
    """Stop the qbittorrent-nox systemd service."""
    try:
        run_cmd(["systemctl", "stop", "qbittorrent-nox"], capture_output=False)
        logging.info("Stopped qbittorrent-nox service")
    except Exception as e:
        logging.error(f"Failed to stop qbittorrent-nox: {e}")
