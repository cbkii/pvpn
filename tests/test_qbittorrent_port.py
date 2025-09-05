import pvpn.qbittorrent as qb
from pvpn.config import Config


class DummyResp:
    def __init__(self, data=None):
        self._data = data or {}

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


def test_get_listen_port_webui(monkeypatch):
    cfg = Config(config_dir="/tmp/pvpn-test1")

    class DummySession:
        def post(self, *args, **kwargs):
            return DummyResp()

        def get(self, *args, **kwargs):
            return DummyResp({"listen_port": 1111})

    monkeypatch.setattr(qb.requests, "Session", lambda: DummySession())
    assert qb.get_listen_port(cfg) == 1111


def test_get_listen_port_config_fallback(tmp_path, monkeypatch):
    cfg = Config(config_dir=tmp_path / "cfg")
    cfg.qb_enable = False  # skip API

    conf_dir = tmp_path / ".config" / "qBittorrent"
    conf_dir.mkdir(parents=True)
    conf_file = conf_dir / "qBittorrent.conf"
    conf_file.write_text("[Preferences]\nConnection\\PortRangeMin=4242\n")

    monkeypatch.setattr(qb.Path, "home", lambda: tmp_path)
    assert qb.get_listen_port(cfg) == 4242


def test_get_listen_port_ss_fallback(tmp_path, monkeypatch):
    cfg = Config(config_dir=tmp_path / "cfg")
    cfg.qb_enable = False  # skip API

    monkeypatch.setattr(qb.Path, "home", lambda: tmp_path)  # no config file

    ss_output = "LISTEN 0 128 0.0.0.0:5678 *:* users:(\"qbittorrent-nox\",pid=1,fd=1)\n"
    monkeypatch.setattr(
        qb.subprocess, "check_output", lambda *a, **k: ss_output.encode()
    )

    assert qb.get_listen_port(cfg) == 5678


def test_get_listen_port_default(tmp_path, monkeypatch):
    cfg = Config(config_dir=tmp_path / "cfg")
    cfg.qb_enable = False

    monkeypatch.setattr(qb.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(
        qb.subprocess, "check_output", lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError())
    )

    assert qb.get_listen_port(cfg) == cfg.qb_port
