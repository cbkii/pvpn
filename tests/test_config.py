# tests/test_config.py

import os
from pathlib import Path
import tempfile
import pytest
from pvpn.config import Config

def test_config_save_load(tmp_path):
    cfg_dir = tmp_path / "cfg"
    # Initialize new config
    cfg = Config(config_dir=str(cfg_dir))
    cfg.proton_user = "alice"
    cfg.proton_pass = "secret"
    cfg.qb_port = 12345
    cfg.monitor_interval = 30
    cfg.monitor_failures = 5
    cfg.monitor_latency_threshold = 800
    cfg.save()

    # Load fresh and verify
    cfg2 = Config.load(config_dir=str(cfg_dir))
    assert cfg2.proton_user == "alice"
    assert cfg2.proton_pass == "secret"
    assert cfg2.qb_port == 12345
    assert cfg2.monitor_interval == 30
    assert cfg2.monitor_failures == 5
    assert cfg2.monitor_latency_threshold == 800

def test_tunnel_rules(tmp_path):
    cfg_dir = tmp_path / "cfg"
    cfg = Config(config_dir=str(cfg_dir))
    # Initially empty
    rules = cfg.load_tunnel_rules()
    assert rules == {"processes": [], "pids": [], "ips": []}

    # Save some rules
    new_rules = {"processes": ["qbittorrent-nox"], "pids": [999], "ips": ["1.2.3.4"]}
    cfg.save_tunnel_rules(new_rules)
    loaded = cfg.load_tunnel_rules()
    assert loaded == new_rules
