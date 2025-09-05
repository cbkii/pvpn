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
    cfg.save()

    # Load fresh and verify
    cfg2 = Config.load(config_dir=str(cfg_dir))
    assert cfg2.proton_user == "alice"
    assert cfg2.proton_pass == "secret"
    assert cfg2.qb_port == 12345

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


def test_env_config_dir(monkeypatch, tmp_path):
    env_dir = tmp_path / "envcfg"
    monkeypatch.setenv("PVPN_CONFIG_DIR", str(env_dir))
    cfg = Config()
    assert cfg.config_dir == env_dir


def test_chown_to_invoker(monkeypatch, tmp_path):
    """Config operations should chown files to the invoking user when run as root."""
    cfg_dir = tmp_path / "cfg"

    # Simulate running under sudo as UID/GID 1000
    monkeypatch.setenv("SUDO_UID", "1000")
    monkeypatch.setenv("SUDO_GID", "1000")
    monkeypatch.setattr(os, "geteuid", lambda: 0)

    chowned = []

    def fake_chown(path, uid, gid):
        chowned.append((Path(path), uid, gid))

    monkeypatch.setattr(os, "chown", fake_chown)

    cfg = Config(config_dir=str(cfg_dir))
    cfg.save()
    cfg.save_tunnel_rules({})

    expected = {cfg_dir, cfg.ini_path, cfg.tunnel_json_path}
    seen = {p for p, _, _ in chowned}
    assert expected.issubset(seen)
