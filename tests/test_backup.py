"""Tests for backup/restore."""

from claude_lean.common.backup import (
    make_snapshot,
    latest_snapshot,
    list_snapshots,
    load_manifest,
    restore_snapshot,
)


def test_snapshot_creates_directory(fake_claude_home):
    snap = make_snapshot(fake_claude_home, [fake_claude_home.global_claude_md], reason="test")
    assert snap.is_dir()


def test_snapshot_manifest_records_files(fake_claude_home):
    snap = make_snapshot(fake_claude_home, [fake_claude_home.global_claude_md], reason="test")
    manifest = load_manifest(snap)
    assert manifest is not None
    assert "CLAUDE.md" in manifest.files
    assert manifest.reason == "test"


def test_list_snapshots_newest_first(fake_claude_home):
    snap1 = make_snapshot(fake_claude_home, [fake_claude_home.global_claude_md], reason="a")
    snap2 = make_snapshot(fake_claude_home, [fake_claude_home.global_claude_md], reason="b")
    snaps = list_snapshots(fake_claude_home)
    assert len(snaps) >= 2
    # snap2 is more recent
    assert snaps[0].name >= snap1.name


def test_latest_snapshot(fake_claude_home):
    assert latest_snapshot(fake_claude_home) is None
    snap = make_snapshot(fake_claude_home, [fake_claude_home.global_claude_md], reason="test")
    assert latest_snapshot(fake_claude_home) == snap


def test_restore_roundtrip(fake_claude_home):
    # Snapshot original
    original = fake_claude_home.global_claude_md.read_text()
    snap = make_snapshot(fake_claude_home, [fake_claude_home.global_claude_md], reason="test")

    # Mutate
    fake_claude_home.global_claude_md.write_text("CORRUPTED")
    assert fake_claude_home.global_claude_md.read_text() == "CORRUPTED"

    # Restore
    restored = restore_snapshot(fake_claude_home, snap)
    assert len(restored) == 1
    assert fake_claude_home.global_claude_md.read_text() == original
