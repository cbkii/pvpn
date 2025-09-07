import pvpn.wireguard as wg


def test_adds_ipv6(tmp_path):
    conf = tmp_path / 'wg.conf'
    conf.write_text('[Interface]\nAllowedIPs = 0.0.0.0/0\n')
    wg.ensure_ipv6_allowed(str(conf))
    assert 'AllowedIPs = 0.0.0.0/0, ::/0' in conf.read_text()


def test_no_duplicate(tmp_path):
    conf = tmp_path / 'wg.conf'
    conf.write_text('[Interface]\nAllowedIPs = 0.0.0.0/0, ::/0\n')
    wg.ensure_ipv6_allowed(str(conf))
    content = conf.read_text()
    assert content.count('::/0') == 1
