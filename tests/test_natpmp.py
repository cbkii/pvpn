import os
import argparse
import types
import subprocess
import sys
from pathlib import Path

import pytest

from pvpn import natpmp, protonvpn
from pvpn.config import Config


def test_request_mapping_success(monkeypatch):
    def fake_check_output(cmd, stderr=None, timeout=None):
        return b"header\nMapped public port 4321\n"
    monkeypatch.setattr(subprocess, "check_output", fake_check_output)
    port = natpmp._request_mapping("1.2.3.4", 1234)
    assert port == 4321


def test_start_forward_log_fallback(monkeypatch, tmp_path):
    # prepare config and log
    log = tmp_path / "pvpn.log"
    log.write_text("x\nPort pair 6000 1234\n")
    cfg = Config(config_dir=str(tmp_path))
    cfg.qb_port = 1234
    monkeypatch.setattr(Config, "load", classmethod(lambda cls: cfg))
    monkeypatch.setattr(natpmp, "_get_vpn_gateway", lambda iface: "1.1.1.1")

    def fake_check_output(cmd, stderr=None, timeout=None):
        return b"no mapping"  # triggers fallback
    monkeypatch.setattr(subprocess, "check_output", fake_check_output)

    port = natpmp.start_forward("wg0")
    assert port == 6000


def test_start_forward_failure(monkeypatch, tmp_path):
    cfg = Config(config_dir=str(tmp_path))
    cfg.qb_port = 1234
    monkeypatch.setattr(Config, "load", classmethod(lambda cls: cfg))
    monkeypatch.setattr(natpmp, "_get_vpn_gateway", lambda iface: "1.1.1.1")

    def fake_check_output(cmd, stderr=None, timeout=None):
        return b"no mapping"  # no log fallback
    monkeypatch.setattr(subprocess, "check_output", fake_check_output)

    port = natpmp.start_forward("wg0")
    assert port == 0


def test_start_forward_qbittorrent_log_fallback(monkeypatch, tmp_path):
    cfg = Config(config_dir=str(tmp_path))
    cfg.qb_port = 1234
    monkeypatch.setattr(Config, "load", classmethod(lambda cls: cfg))
    monkeypatch.setattr(natpmp, "_get_vpn_gateway", lambda iface: "1.1.1.1")

    def fake_check_output(cmd, stderr=None, timeout=None):
        return b"no mapping"
    monkeypatch.setattr(subprocess, "check_output", fake_check_output)

    # ensure pvpn.log absent to force qb log fallback
    qb_log_dir = tmp_path / ".local" / "share" / "qBittorrent" / "logs"
    qb_log_dir.mkdir(parents=True)
    (qb_log_dir / "qbittorrent.log").write_text("Port mapping successful, port: 7777\n")
    monkeypatch.setattr(natpmp.Path, "home", lambda: tmp_path)

    port = natpmp.start_forward("wg0")
    assert port == 7777

def _setup_connect_env(monkeypatch, tmp_path):
    cfg = Config(config_dir=str(tmp_path))
    cfg.qb_port = 1234
    monkeypatch.setattr(Config, "load", classmethod(lambda cls: cfg))
    args = argparse.Namespace(cc=None, sc=False, p2p=False, fastest=None,
                              threshold=None, dns=None, ks=None, latency_cutoff=None)
    wg_dir = tmp_path / "wireguard"
    wg_dir.mkdir()
    (wg_dir / "wgpxx1.conf").write_text("[Interface]\nPrivateKey = x\n")

    monkeypatch.setattr(protonvpn, "load_token", lambda cfg: "t")
    monkeypatch.setattr(protonvpn, "fetch_servers", lambda token: [{"NameCode": "xx", "ID": 1, "Name": "srv", "Load": 10, "UDP": "1.1.1.1:1"}])
    monkeypatch.setattr(protonvpn, "filter_servers", lambda servers, cc, sc, p2p, thr: servers)
    monkeypatch.setattr(protonvpn, "select_fastest", lambda servers, method, cutoff=None: servers[0])
    monkeypatch.setitem(sys.modules, 'pvpn.wireguard', types.SimpleNamespace(bring_up=lambda cf, dns=True: 'wg0'))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    return cfg, args


def test_connect_aborts_without_port_forwarding(monkeypatch, tmp_path):
    cfg, args = _setup_connect_env(monkeypatch, tmp_path)
    monkeypatch.setattr(natpmp, "_get_vpn_gateway", lambda iface: "1.1.1.1")
    def fake_check_output(cmd, stderr=None, timeout=None):
        return b"no mapping"
    monkeypatch.setattr(subprocess, "check_output", fake_check_output)
    with pytest.raises(SystemExit):
        protonvpn.connect(cfg, args)


def test_connect_updates_qbittorrent_on_success(monkeypatch, tmp_path):
    cfg, args = _setup_connect_env(monkeypatch, tmp_path)
    monkeypatch.setattr(natpmp, "_get_vpn_gateway", lambda iface: "1.1.1.1")
    def fake_check_output(cmd, stderr=None, timeout=None):
        return b"Mapped public port 4321"
    monkeypatch.setattr(subprocess, "check_output", fake_check_output)
    called = {}
    def fake_update_port(cfg_arg, port):
        called['port'] = port
    monkeypatch.setitem(sys.modules, 'pvpn.qbittorrent', types.SimpleNamespace(update_port=fake_update_port))
    protonvpn.connect(cfg, args)
    assert called.get('port') == 4321
