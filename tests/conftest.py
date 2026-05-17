"""Shared pytest fixtures."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from claude_lean.common.claude_paths import ClaudePaths


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fake_claude_home(tmp_path: Path) -> ClaudePaths:
    """Copy the fixture ~/.claude/ into a temp dir and return ClaudePaths."""
    src = FIXTURES_DIR / "fake_claude_home"
    dst = tmp_path / ".claude"
    shutil.copytree(src, dst)
    return ClaudePaths(home=dst)
