# pvpn/config.py

import configparser
import getpass
import logging
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

        # Load existing config if available without recursion
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
        return cls(config_dir)

    def _read_ini(self):
        """Internal helper to populate fields from config.ini."""
        self.parser.read(self.ini_path)
        # ProtonVPN section
        if 'protonvpn' in self.parser:
            sec = self.parser['protonvpn']
            self.proton_user = sec.get('user', self.proton_user)
            self.proton_pass = sec.get('pass', self.proton_pass)
            self.proton_2fa = sec.get('2fa', self.proton_2fa)
            self.wireguard_port = sec.getint('wireguard_port', self.wireguard_port)
            self.session_dir = sec.get('session_dir', self.session_dir)
        # qBittorrent section
        if 'qbittorrent' in self.parser:
            sec = self.parser['qbittorrent']
            self.qb_enable = sec.getboolean('enable', self.qb_enable)
            self.qb_url = sec.get('url', self.qb_url)
            self.qb_user = sec.get('user', self.qb_user)
            self.qb_pass = sec.get('pass', self.qb_pass)
            self.qb_port = sec.getint('port', self.qb_port)
        # Network defaults
        if 'network' in self.parser:
            sec = self.parser['network']
            self.network_ks_default = sec.getboolean('ks_default', self.network_ks_default)
            self.network_dns_default = sec.getboolean('dns_default', self.network_dns_default)
            self.network_threshold_default = sec.getint('threshold_default', self.network_threshold_default)
        # Tunnel JSON path
        if 'tunnel' in self.parser:
            sec = self.parser['tunnel']
            self.tunnel_json_path = Path(sec.get('tunnel_json_path', str(self.tunnel_json_path)))

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
        # Write file
        try:
            with open(self.ini_path, 'w') as f:
                self.parser.write(f)
        except Exception as e:
            logging.error(f"Cannot write config to {self.ini_path}: {e}")

    def interactive_setup(self, proton=False, qb=False, network=False):
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
            self.qb_user = input(f"WebUI username [{self.qb_user}]: ") or self.qb_user
            self.qb_pass = getpass.getpass("WebUI password: ") or self.qb_pass
            port = input(f"Listen port [{self.qb_port}]: ") or str(self.qb_port)
            self.qb_port = int(port)

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
