"""Locate and validate the user's ~/.claude/ directory and its sub-paths."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ClaudePaths:
    """Resolved paths inside a user's ~/.claude/ directory.

    Construct via ``ClaudePaths.discover()`` for the default location,
    or pass ``home=Path(...)`` for tests or non-default installs.
    """

    home: Path

    @classmethod
    def discover(cls, override: Path | None = None) -> "ClaudePaths":
        """Find ~/.claude/, honoring ``override`` or $CLAUDE_HOME if set."""
        if override is not None:
            return cls(home=override.expanduser().resolve())
        env = os.environ.get("CLAUDE_HOME")
        if env:
            return cls(home=Path(env).expanduser().resolve())
        return cls(home=(Path.home() / ".claude").resolve())

    # ---- top-level files ----

    @property
    def global_claude_md(self) -> Path:
        return self.home / "CLAUDE.md"

    @property
    def settings_json(self) -> Path:
        return self.home / "settings.json"

    @property
    def settings_local_json(self) -> Path:
        return self.home / "settings.local.json"

    # ---- subdirs ----

    @property
    def projects_dir(self) -> Path:
        return self.home / "projects"

    @property
    def plugins_cache(self) -> Path:
        return self.home / "plugins" / "cache"

    @property
    def backups_dir(self) -> Path:
        return self.home / ".claude-lean-backups"

    # ---- helpers ----

    def project_memory_dir(self, project_cwd: Path) -> Path:
        """Memory dir for a given project absolute path."""
        encoded = encode_project_path(project_cwd)
        return self.projects_dir / encoded / "memory"

    def project_memory_index(self, project_cwd: Path) -> Path:
        return self.project_memory_dir(project_cwd) / "MEMORY.md"

    def exists(self) -> bool:
        return self.home.is_dir()

    def __str__(self) -> str:
        return str(self.home)


def encode_project_path(project_cwd: Path) -> str:
    """Encode an absolute project path the same way Claude Code does.

    Example: ``/Users/vipin/Downloads/Opensource`` → ``-Users-vipin-Downloads-Opensource``
    """
    abs_path = str(project_cwd.resolve())
    return abs_path.replace(os.sep, "-")


def decode_project_path(encoded: str) -> Path:
    """Best-effort inverse of ``encode_project_path``.

    Note: lossy if any original path component contained a literal '-'.
    Used for display only; never for filesystem access.
    """
    return Path(encoded.replace("-", os.sep))
