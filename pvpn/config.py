# pvpn/config.py

import configparser
import json
import getpass
import logging
import os
import base64
import hashlib
from urllib.parse import urlparse
from pathlib import Path

class Config:
    """
    Manages loading, saving, and interactive setup of pvpn configuration.
    - Stores settings in ~/.pvpn-cli/pvpn/config.ini
    """

    def __init__(self, config_dir=None):
        # Base directory for configs
        self.config_dir = Path(config_dir or Path.home() / ".pvpn-cli" / "pvpn")
        self.config_dir.mkdir(parents=True, exist_ok=True)

        self.ini_path = self.config_dir / "config.ini"
        self.parser = configparser.ConfigParser()

        # Default settings
        self.proton_user = ""
        self.proton_pass = ""
        self.proton_2fa = ""
        self.wireguard_port = 51820
        self.session_dir = str(self.config_dir)

        self.qb_enable = True
        self.qb_url = "http://127.0.0.1:8080"
        self.qb_user = "pipi"
        self.qb_pass = ""
        self.qb_port = 6881

        self.network_ks_default = False
        self.network_dns_default = True
        self.network_threshold_default = 60


        # Monitoring defaults
        self.monitor_interval = 60
        self.monitor_failures = 3
        self.monitor_latency_threshold = 500

        # Load existing config if available

        try:
            if self.ini_path.exists():
                self._read_ini()
        except Exception as e:
            logging.warning(f"Could not load existing config: {e}")

    @classmethod
    def load(cls, config_dir=None):
        """
        Instantiate a Config, automatically loading from config.ini if present.
        """

        cfg = cls(config_dir)
        if cfg.ini_path.exists():
            try:
                cfg.parser.read(cfg.ini_path)
                # ProtonVPN section
                if 'protonvpn' in cfg.parser:
                    sec = cfg.parser['protonvpn']
                    cfg.proton_user = sec.get('user', cfg.proton_user)
                    cfg.proton_pass = sec.get('pass', cfg.proton_pass)
                    cfg.proton_2fa = sec.get('2fa', cfg.proton_2fa)
                    cfg.wireguard_port = sec.getint('wireguard_port', cfg.wireguard_port)
                    cfg.session_dir = sec.get('session_dir', cfg.session_dir)
                # qBittorrent section
                if 'qbittorrent' in cfg.parser:
                    sec = cfg.parser['qbittorrent']
                    cfg.qb_enable = sec.getboolean('enable', cfg.qb_enable)
                    cfg.qb_url = sec.get('url', cfg.qb_url)
                    cfg.qb_user = sec.get('user', cfg.qb_user)
                    cfg.qb_pass = sec.get('pass', cfg.qb_pass)
                    cfg.qb_port = sec.getint('port', cfg.qb_port)

                # Network defaults
                if 'network' in cfg.parser:
                    sec = cfg.parser['network']
                    cfg.network_ks_default = sec.getboolean('ks_default', cfg.network_ks_default)
                    cfg.network_dns_default = sec.getboolean('dns_default', cfg.network_dns_default)
                    cfg.network_threshold_default = sec.getint('threshold_default', cfg.network_threshold_default)
                # Monitor defaults
                if 'monitor' in cfg.parser:
                    sec = cfg.parser['monitor']
                    cfg.monitor_interval = sec.getint('interval', cfg.monitor_interval)
                    cfg.monitor_failures = sec.getint('failures', cfg.monitor_failures)
                    cfg.monitor_latency_threshold = sec.getint('latency_threshold', cfg.monitor_latency_threshold)
    return cfg



    def save(self):
        """
        Write the current settings to config.ini.
        """
        # Build sections
        self.parser['protonvpn'] = {
            'user': self.proton_user,
            'pass': self.proton_pass,
            '2fa': self.proton_2fa,
            'wireguard_port': str(self.wireguard_port),
            'session_dir': self.session_dir
        }
        self.parser['qbittorrent'] = {
            'enable': str(self.qb_enable),
            'url': self.qb_url,
            'user': self.qb_user,
            'pass': self.qb_pass,
            'port': str(self.qb_port)
        }

        self.parser['network'] = {
            'ks_default': str(self.network_ks_default),
            'dns_default': str(self.network_dns_default),
            'threshold_default': str(self.network_threshold_default)
        }

        self.parser['monitor'] = {
            'interval': str(self.monitor_interval),
            'failures': str(self.monitor_failures),
            'latency_threshold': str(self.monitor_latency_threshold)
        }

        # Write file
        try:
            with open(self.ini_path, 'w') as f:
                self.parser.write(f)
        except Exception as e:
            logging.error(f"Cannot write config to {self.ini_path}: {e}")


    def load_tunnel_rules(self):
        """
        Load split-tunnel rules from JSON, return defaults on error.
        """
        try:
            if self.tunnel_json_path.exists():
                return json.loads(self.tunnel_json_path.read_text())
        except Exception as e:
            logging.error(f"Failed to load tunnel rules: {e}")
        return {"processes": [], "pids": [], "ips": []}

    def save_tunnel_rules(self, rules):
        """
        Save split-tunnel rules to JSON.
        """
        try:
            with open(self.tunnel_json_path, 'w') as f:
                json.dump(rules, f, indent=2)
        except Exception as e:
            logging.error(f"Failed to save tunnel rules: {e}")

    @staticmethod
    def _qb_pass_hash(password: str) -> str:
        """
        Generate qBittorrent WebUI PBKDF2 password hash.
        """
        salt = os.urandom(16)
        key = hashlib.pbkdf2_hmac('sha512', password.encode(), salt, 100000, dklen=64)
        return f"{base64.b64encode(salt).decode()}:{base64.b64encode(key).decode()}"

    def _enable_qb_webui(self):
        """
        Ensure qBittorrent's WebUI is enabled locally with stored credentials.
        Requires a manual restart of qbittorrent-nox to take effect.
        """
        conf_path = Path.home() / ".config" / "qBittorrent" / "qBittorrent.conf"
        if not conf_path.exists():
            logging.warning(f"qBittorrent config not found: {conf_path}")
            return

        parser = configparser.RawConfigParser()
        parser.optionxform = str
        parser.read(conf_path)
        if 'Preferences' not in parser:
            parser.add_section('Preferences')

        url = urlparse(self.qb_url)
        host = url.hostname or '127.0.0.1'
        port = url.port or 8080

        pref = parser['Preferences']
        pref['WebUI\\Enabled'] = 'true'
        pref['WebUI\\Address'] = host
        pref['WebUI\\Port'] = str(port)
        pref['WebUI\\Username'] = self.qb_user
        if self.qb_pass:
            pref['WebUI\\Password_PBKDF2'] = self._qb_pass_hash(self.qb_pass)

        with open(conf_path, 'w') as f:
            parser.write(f)
        logging.info(f"Enabled qBittorrent WebUI in {conf_path}. Manual restart required.")

        """
        Run interactive prompts for specified components.
        If no flags, configure all.
        """
        # Enable all if none specified
        if not any([proton, qb, network]):
            proton = qb = network = True

        # ProtonVPN configuration
        if proton:
            print("=== ProtonVPN Configuration ===")
            self.proton_user = input(f"ProtonVPN username [{self.proton_user}]: ") or self.proton_user
            self.proton_pass = getpass.getpass("ProtonVPN password: ") or self.proton_pass
            self.proton_2fa = input(f"2FA code (if any) [{self.proton_2fa}]: ") or self.proton_2fa
            port = input(f"WireGuard port [{self.wireguard_port}]: ") or str(self.wireguard_port)
            self.wireguard_port = int(port)
            sd = input(f"Session directory [{self.session_dir}]: ") or self.session_dir
            self.session_dir = sd

        # qBittorrent configuration
        if qb:
            print("=== qBittorrent Configuration ===")
            en = input(f"Enable WebUI API (true/false) [{self.qb_enable}]: ") or str(self.qb_enable)
            self.qb_enable = en.lower() in ("true", "1", "yes", "y")
            self.qb_url = input(f"WebUI URL [{self.qb_url}]: ") or self.qb_url
            parsed = urlparse(self.qb_url)
            if parsed.hostname not in ("127.0.0.1", "localhost"):
                print("Only local WebUI supported; forcing http://127.0.0.1:8080")
                self.qb_url = "http://127.0.0.1:8080"
            self.qb_user = input(f"WebUI username [{self.qb_user}]: ") or self.qb_user
            self.qb_pass = getpass.getpass("WebUI password: ") or self.qb_pass
            port = input(f"Listen port [{self.qb_port}]: ") or str(self.qb_port)
            self.qb_port = int(port)
            if self.qb_enable:
                self._enable_qb_webui()
                print("qBittorrent WebUI configured. Restart qbittorrent-nox once to apply.")

        # Network defaults configuration
        if network:
            print("=== Network Defaults ===")
            ks = input(f"Default kill-switch (true/false) [{self.network_ks_default}]: ") or str(self.network_ks_default)
            self.network_ks_default = ks.lower() in ("true", "1", "yes", "y")
            dns = input(f"Default Proton DNS (true/false) [{self.network_dns_default}]: ") or str(self.network_dns_default)
            self.network_dns_default = dns.lower() in ("true", "1", "yes", "y")
            thr = input(f"Default load threshold (1-100) [{self.network_threshold_default}]: ") or str(self.network_threshold_default)
            self.network_threshold_default = int(thr)

        # Save updated configuration
        self.save()
        print(f"Configuration saved to {self.ini_path}")
