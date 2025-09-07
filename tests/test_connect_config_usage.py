from types import SimpleNamespace
from pvpn.config import Config
import pvpn.protonvpn as pv


class DummyThread:
    def join(self):
        pass


def test_connect_uses_specified_config(tmp_path, monkeypatch):
    cfg = Config()
    cfg.config_dir = str(tmp_path)
    cfg.network_dns_default = True
    cfg.network_ks_default = False
    cfg.qb_enable = False

    wg_dir = tmp_path / "wireguard"
    wg_dir.mkdir()
    conf = wg_dir / "wg0.conf"
    conf.write_text("[Interface]\nAddress = 10.0.0.2/32\nDNS = 1.1.1.1\n")

    args = SimpleNamespace(config=str(conf), dns=None, ks="false")

    monkeypatch.setattr("pvpn.utils.check_root", lambda: None)
    called = {}

    def fake_bring_up(file, dns):
        called["file"] = file
        return "wg0"

    monkeypatch.setattr("pvpn.wireguard.bring_up", fake_bring_up)
    monkeypatch.setattr("pvpn.routing.enable_killswitch", lambda iface: None)
    monkeypatch.setattr("pvpn.natpmp.start_forward", lambda iface: 0)
    monkeypatch.setattr("pvpn.monitor.start_monitor", lambda cfg, iface: DummyThread())
    monkeypatch.setattr("pvpn.qbittorrent.start_service", lambda: None)
    monkeypatch.setattr("pvpn.qbittorrent.update_port", lambda cfg, port: None)

    pv.connect(cfg, args)
    assert called["file"] == str(conf)


def test_connect_uses_first_available_config(tmp_path, monkeypatch):
    cfg = Config()
    cfg.config_dir = str(tmp_path)
    cfg.network_dns_default = True
    cfg.network_ks_default = False
    cfg.qb_enable = False

    wg_dir = tmp_path / "wireguard"
    wg_dir.mkdir()
    first = wg_dir / "a.conf"
    first.write_text("[Interface]\nAddress = 10.0.0.2/32\n")
    (wg_dir / "b.conf").write_text("[Interface]\nAddress = 10.0.0.3/32\n")

    args = SimpleNamespace(config=None, dns=None, ks="false")

    monkeypatch.setattr("pvpn.utils.check_root", lambda: None)
    called = {}

    def fake_bring_up(file, dns):
        called["file"] = file
        return "wg0"

    monkeypatch.setattr("pvpn.wireguard.bring_up", fake_bring_up)
    monkeypatch.setattr("pvpn.routing.enable_killswitch", lambda iface: None)
    monkeypatch.setattr("pvpn.natpmp.start_forward", lambda iface: 0)
    monkeypatch.setattr("pvpn.monitor.start_monitor", lambda cfg, iface: DummyThread())
    monkeypatch.setattr("pvpn.qbittorrent.start_service", lambda: None)
    monkeypatch.setattr("pvpn.qbittorrent.update_port", lambda cfg, port: None)

    pv.connect(cfg, args)
    assert called["file"] == str(first)
