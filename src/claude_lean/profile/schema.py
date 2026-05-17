"""Profile data model + TOML loader."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Profile:
    """A context profile: which plugins to enable, what CLAUDE.md to use, etc."""

    name: str
    display_name: str
    description: str
    version: str
    target_stack: list[str] = field(default_factory=list)
    enabled_plugins: list[str] = field(default_factory=list)
    disabled_plugins: list[str] = field(default_factory=list)
    claude_md_content: str | None = None
    claude_md_mode: str = "replace"  # replace | append | prepend
    source_path: Path | None = None

    @classmethod
    def from_toml_path(cls, path: Path) -> "Profile":
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        plugins = data.get("plugins", {})
        claude_md = data.get("claude_md", {})
        return cls(
            name=data["name"],
            display_name=data.get("display_name", data["name"]),
            description=data.get("description", ""),
            version=data.get("version", "0.0.0"),
            target_stack=data.get("target_stack", []),
            enabled_plugins=plugins.get("enabled", {}).get("plugins", []) if isinstance(plugins.get("enabled"), dict) else plugins.get("enabled", []),
            disabled_plugins=plugins.get("disabled", {}).get("plugins", []) if isinstance(plugins.get("disabled"), dict) else plugins.get("disabled", []),
            claude_md_content=claude_md.get("content"),
            claude_md_mode=claude_md.get("mode", "replace"),
            source_path=path,
        )
