# tests/test_cli.py

from pvpn.cli import build_parser

def test_subcommands_present():
    parser = build_parser()
    help_text = parser.format_help()
    # Check that all subcommands are documented
    for cmd in ["init", "connect", "disconnect", "status", "list"]:
        assert cmd in help_text

def test_connect_alias():
    parser = build_parser()
    args = parser.parse_args(["c"])
    assert args.cmd == "connect"
