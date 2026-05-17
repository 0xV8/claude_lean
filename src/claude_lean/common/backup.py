"""Backup and restore for files we are about to mutate.

Snapshots are stored under ``~/.claude/.claude-lean-backups/{ISO-timestamp}/``
with relative paths preserved under the snapshot root. Each snapshot has a
small ``manifest.json`` recording which files it covers.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from pathlib import Path

from claude_lean.common.claude_paths import ClaudePaths


MANIFEST_NAME = "manifest.json"


@dataclass
class SnapshotManifest:
    """Metadata about a single backup snapshot."""

    timestamp: str  # ISO 8601 UTC
    reason: str
    files: list[str]  # paths relative to ClaudePaths.home

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


def make_snapshot(
    paths: ClaudePaths,
    files: list[Path],
    *,
    reason: str = "manual",
    now: datetime | None = None,
) -> Path:
    """Snapshot the given files. Returns the snapshot root directory.

    Files that don't exist are skipped silently — we only back up what's there.
    Empty file list still creates an (empty) snapshot manifest, useful for
    "I'm about to do nothing" audit trail.
    """
    now = now or datetime.now(timezone.utc)
    # Microsecond granularity so back-to-back snapshots don't collide
    ts = now.strftime("%Y-%m-%dT%H-%M-%S-%fZ")
    snap_root = paths.backups_dir / ts
    snap_root.mkdir(parents=True, exist_ok=True)

    saved: list[str] = []
    for src in files:
        if not src.exists():
            continue
        rel = src.resolve().relative_to(paths.home)
        dst = snap_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
        saved.append(str(rel))

    manifest = SnapshotManifest(timestamp=ts, reason=reason, files=saved)
    (snap_root / MANIFEST_NAME).write_text(manifest.to_json(), encoding="utf-8")
    return snap_root


def list_snapshots(paths: ClaudePaths) -> list[Path]:
    """List all available snapshots, newest first."""
    if not paths.backups_dir.is_dir():
        return []
    snaps = [p for p in paths.backups_dir.iterdir() if p.is_dir()]
    return sorted(snaps, reverse=True)


def latest_snapshot(paths: ClaudePaths) -> Path | None:
    snaps = list_snapshots(paths)
    return snaps[0] if snaps else None


def load_manifest(snapshot_root: Path) -> SnapshotManifest | None:
    mf = snapshot_root / MANIFEST_NAME
    if not mf.is_file():
        return None
    raw = json.loads(mf.read_text(encoding="utf-8"))
    return SnapshotManifest(**raw)


def restore_snapshot(paths: ClaudePaths, snapshot_root: Path) -> list[Path]:
    """Restore files from a snapshot. Returns list of restored paths.

    Files in the snapshot overwrite current files. Files NOT in the snapshot
    are left untouched — this is restore, not delete.
    """
    manifest = load_manifest(snapshot_root)
    if manifest is None:
        raise ValueError(f"no manifest at {snapshot_root}")

    restored: list[Path] = []
    for rel in manifest.files:
        src = snapshot_root / rel
        dst = paths.home / rel
        if not src.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
        restored.append(dst)
    return restored
