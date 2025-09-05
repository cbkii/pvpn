import pvpn.protonvpn as pv
from pvpn.config import Config


def test_status_reports_all(monkeypatch, capsys):
    cfg = Config()
    monkeypatch.setattr('pvpn.wireguard.get_active_iface', lambda: 'wgpTEST0')
    monkeypatch.setattr('pvpn.wireguard.get_dns_servers', lambda: ['1.1.1.1', '9.9.9.9'])
    monkeypatch.setattr('pvpn.routing.killswitch_status', lambda: True)
    monkeypatch.setattr('pvpn.natpmp.get_public_port', lambda iface, port: 12345)
    monkeypatch.setattr('pvpn.qbittorrent.get_listen_port', lambda cfg: 6881)

    pv.status(cfg)
    out = capsys.readouterr().out
    assert 'Interface: wgpTEST0' in out
    assert 'DNS: 1.1.1.1, 9.9.9.9' in out
    assert 'Kill-switch: enabled' in out
    assert 'Forwarded port: 12345' in out
    assert 'qBittorrent port: 6881' in out
