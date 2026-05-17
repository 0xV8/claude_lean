"""Smoke tests for the CLI entry point."""

import json
from pathlib import Path

from claude_lean.cli import main


def test_help_exits_zero(capsys):
    try:
        main(["--help"])
    except SystemExit as exc:
        assert exc.code == 0
    captured = capsys.readouterr()
    assert "claude-lean" in captured.out


def test_audit_runs_on_fixture(fake_claude_home, capsys):
    code = main(["--claude-home", str(fake_claude_home.home), "audit"])
    assert code == 0
    captured = capsys.readouterr()
    out = captured.out
    assert "Plugins enabled" in out or "Findings" in out


def test_audit_json_output(fake_claude_home, capsys, tmp_path):
    out_path = tmp_path / "audit.json"
    code = main(
        [
            "--claude-home",
            str(fake_claude_home.home),
            "audit",
            "--json-out",
            str(out_path),
        ]
    )
    assert code == 0
    data = json.loads(out_path.read_text())
    assert data["schema_version"] == 1
    assert "totals" in data
    assert "findings" in data


def test_profile_list_runs(fake_claude_home, capsys):
    code = main(["--claude-home", str(fake_claude_home.home), "profile", "list"])
    assert code == 0
    out = capsys.readouterr().out
    assert "python-ml" in out
    assert "frontend-web" in out


def test_apply_dry_run_does_not_modify_files(fake_claude_home, capsys):
    original_claude_md = fake_claude_home.global_claude_md.read_text()
    original_settings = fake_claude_home.settings_json.read_text()

    code = main(
        ["--claude-home", str(fake_claude_home.home), "apply", "--dry-run", "--yes"]
    )
    assert code == 0
    assert fake_claude_home.global_claude_md.read_text() == original_claude_md
    assert fake_claude_home.settings_json.read_text() == original_settings


def test_restore_list_empty(fake_claude_home, capsys):
    code = main(
        ["--claude-home", str(fake_claude_home.home), "restore", "--list"]
    )
    assert code == 0
