"""Profile manager: list / use / restore."""

from __future__ import annotations

import importlib.resources as ilr
from dataclasses import dataclass
from pathlib import Path

from claude_lean.common.claude_paths import ClaudePaths
from claude_lean.profile.schema import Profile


_STOCK_PACKAGE = "claude_lean.profile.stock"


@dataclass
class ProfileManager:
    paths: ClaudePaths

    def list_stock(self) -> list[Profile]:
        """List all bundled stock profiles."""
        out: list[Profile] = []
        try:
            resources = ilr.files(_STOCK_PACKAGE)
        except (ModuleNotFoundError, FileNotFoundError):
            return out
        for entry in resources.iterdir():
            if entry.name.endswith(".toml"):
                with ilr.as_file(entry) as fp:
                    out.append(Profile.from_toml_path(Path(fp)))
        return sorted(out, key=lambda p: p.name)

    def get(self, name: str) -> Profile | None:
        """Lookup a stock profile by name."""
        for p in self.list_stock():
            if p.name == name:
                return p
        return None

    def apply(self, profile: Profile) -> dict:
        """Apply a profile in-memory: returns dict of changes (not yet written)."""
        # Read current settings
        import json
        settings: dict = {}
        if self.paths.settings_json.is_file():
            try:
                settings = json.loads(self.paths.settings_json.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                settings = {}

        plugins = dict(settings.get("enabledPlugins", {}))

        # Apply enables/disables (by plugin name; preserve marketplace suffix)
        for key in list(plugins.keys()):
            plugin_name = key.split("@", 1)[0]
            if plugin_name in profile.enabled_plugins:
                plugins[key] = True
            elif plugin_name in profile.disabled_plugins:
                plugins[key] = False
        settings["enabledPlugins"] = plugins

        # Compute new CLAUDE.md
        old_claude_md = self.paths.global_claude_md.read_text(encoding="utf-8") if self.paths.global_claude_md.is_file() else ""
        new_claude_md = old_claude_md
        if profile.claude_md_content is not None:
            content = profile.claude_md_content.strip() + "\n"
            if profile.claude_md_mode == "replace":
                new_claude_md = content
            elif profile.claude_md_mode == "append":
                new_claude_md = (old_claude_md.rstrip() + "\n\n" + content).lstrip()
            elif profile.claude_md_mode == "prepend":
                new_claude_md = (content + "\n" + old_claude_md.lstrip()).rstrip() + "\n"

        return {
            "new_settings": settings,
            "old_settings": json.loads(self.paths.settings_json.read_text(encoding="utf-8")) if self.paths.settings_json.is_file() else {},
            "new_claude_md": new_claude_md,
            "old_claude_md": old_claude_md,
            "profile_name": profile.name,
        }
