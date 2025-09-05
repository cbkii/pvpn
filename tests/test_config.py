# tests/test_config.py

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

    mode = cfg.ini_path.stat().st_mode & 0o777
    assert mode == 0o600

    # Load fresh and verify
    cfg2 = Config.load(config_dir=str(cfg_dir))
    assert cfg2.proton_user == "alice"
    assert cfg2.proton_pass == "secret"
    assert cfg2.qb_port == 12345
    assert cfg2.monitor_interval == 30
    assert cfg2.monitor_failures == 5
    assert cfg2.monitor_latency_threshold == 800

