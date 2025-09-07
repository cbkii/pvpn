import re
import pvpn.protonvpn as pv
from pvpn.config import Config

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(s: str) -> str:
    return ANSI_RE.sub("", s)


def test_status_reports_all(monkeypatch, capsys):
    cfg = Config()
    monkeypatch.setattr('pvpn.wireguard.get_active_iface', lambda: 'wgpTEST0')
    monkeypatch.setattr('pvpn.wireguard.get_dns_servers', lambda: ['1.1.1.1', '9.9.9.9'])
    monkeypatch.setattr('pvpn.routing.killswitch_status', lambda: True)
    monkeypatch.setattr('pvpn.natpmp.get_public_port', lambda iface: 12345)
    monkeypatch.setattr('pvpn.qbittorrent.get_listen_port', lambda cfg: 6881)

    pv.status(cfg)
    out_lines = strip_ansi(capsys.readouterr().out).splitlines()
    assert out_lines[0].startswith('✔ Interface') and out_lines[0].endswith('wgpTEST0')
    assert out_lines[1].startswith('✔ DNS') and out_lines[1].endswith('1.1.1.1, 9.9.9.9')
    assert out_lines[2].startswith('✔ Kill-switch') and out_lines[2].endswith('enabled')
    assert out_lines[3].startswith('✔ Forwarded port') and out_lines[3].endswith('12345')
    assert out_lines[4].startswith('✔ qBittorrent port') and out_lines[4].endswith('6881')
