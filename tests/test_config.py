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

