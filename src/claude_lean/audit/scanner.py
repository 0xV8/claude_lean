"""Walk ~/.claude/ and produce an inventory of files we care about.

The scanner is the eyes of the audit subsystem. It is pure data discovery:
it does not interpret, does not score, does not opine. It just builds a
typed inventory that downstream rules consume.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from claude_lean.common.claude_paths import ClaudePaths
from claude_lean.common.tokenizer import count_file_tokens


@dataclass
class FileInfo:
    """One file on disk with a measured token cost."""

    path: Path
    size_bytes: int
    tokens: int

    @classmethod
    def from_path(cls, path: Path) -> "FileInfo":
        size = path.stat().st_size if path.is_file() else 0
        return cls(path=path, size_bytes=size, tokens=count_file_tokens(path))


@dataclass
class PluginInfo:
    """An installed plugin with its files and aggregate token cost."""

    name: str  # e.g. "engineering-skills"
    marketplace: str  # e.g. "claude-code-skills"
    root: Path
    enabled: bool
    skills: list[FileInfo] = field(default_factory=list)
    agents: list[FileInfo] = field(default_factory=list)
    mcp_manifests: list[FileInfo] = field(default_factory=list)

    @property
    def tokens_skills(self) -> int:
        return sum(f.tokens for f in self.skills)

    @property
    def tokens_agents(self) -> int:
        return sum(f.tokens for f in self.agents)

    @property
    def tokens_mcp(self) -> int:
        return sum(f.tokens for f in self.mcp_manifests)

    @property
    def tokens_total(self) -> int:
        return self.tokens_skills + self.tokens_agents + self.tokens_mcp


@dataclass
class MemoryFileInfo:
    """A single memory file with parsed frontmatter where available."""

    path: Path
    tokens: int
    description: str | None
    type_: str | None
    body_excerpt: str  # first ~500 chars for analyzers to inspect


@dataclass
class Inventory:
    """The full audit inventory."""

    claude_home: Path
    claude_md_path: Path | None  # global CLAUDE.md
    claude_md_tokens: int
    settings: dict[str, Any]
    enabled_plugins: list[str]  # from settings.json
    plugins: list[PluginInfo]
    memory_indexes: dict[str, FileInfo]  # project_encoded -> MEMORY.md FileInfo
    memory_files: dict[str, list[MemoryFileInfo]]  # project_encoded -> [memories]

    @property
    def total_skill_tokens(self) -> int:
        return sum(p.tokens_skills for p in self.plugins if p.enabled)

    @property
    def total_agent_tokens(self) -> int:
        return sum(p.tokens_agents for p in self.plugins if p.enabled)

    @property
    def total_mcp_tokens(self) -> int:
        return sum(p.tokens_mcp for p in self.plugins if p.enabled)

    @property
    def estimated_system_prompt_tokens(self) -> int:
        """Estimated controllable contribution to the system prompt per turn."""
        return (
            self.total_skill_tokens
            + self.total_agent_tokens
            + self.total_mcp_tokens
            + self.claude_md_tokens
        )


# ---- public scan entry point ----


def scan(paths: ClaudePaths) -> Inventory:
    """Build a complete inventory of the user's ~/.claude/."""
    settings = _load_settings(paths)
    enabled_plugins = _extract_enabled_plugins(settings)

    plugins = _scan_plugins(paths, enabled_plugins)

    claude_md_path = paths.global_claude_md if paths.global_claude_md.is_file() else None
    claude_md_tokens = count_file_tokens(claude_md_path) if claude_md_path else 0

    memory_indexes, memory_files = _scan_memories(paths)

    return Inventory(
        claude_home=paths.home,
        claude_md_path=claude_md_path,
        claude_md_tokens=claude_md_tokens,
        settings=settings,
        enabled_plugins=enabled_plugins,
        plugins=plugins,
        memory_indexes=memory_indexes,
        memory_files=memory_files,
    )


# ---- internals ----


def _load_settings(paths: ClaudePaths) -> dict[str, Any]:
    if not paths.settings_json.is_file():
        return {}
    try:
        return json.loads(paths.settings_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _extract_enabled_plugins(settings: dict[str, Any]) -> list[str]:
    raw = settings.get("enabledPlugins", {})
    if not isinstance(raw, dict):
        return []
    # Keys look like "engineering-skills@claude-code-skills"
    return [k for k, v in raw.items() if v]


def _scan_plugins(paths: ClaudePaths, enabled: list[str]) -> list[PluginInfo]:
    """Walk plugins/cache/{marketplace}/{plugin}/ and build PluginInfo list."""
    if not paths.plugins_cache.is_dir():
        return []

    enabled_set = set(enabled)  # entries like "engineering-skills@claude-code-skills"
    out: list[PluginInfo] = []

    for marketplace_dir in sorted(paths.plugins_cache.iterdir()):
        if not marketplace_dir.is_dir():
            continue
        marketplace = marketplace_dir.name
        for plugin_dir in sorted(marketplace_dir.iterdir()):
            if not plugin_dir.is_dir():
                continue
            plugin_name = plugin_dir.name
            enabled_key = f"{plugin_name}@{marketplace}"
            is_enabled = enabled_key in enabled_set

            skills = _collect_files(plugin_dir, "SKILL.md")
            agents = _collect_agent_files(plugin_dir)
            mcp = _collect_files(plugin_dir, "mcp.json")

            out.append(
                PluginInfo(
                    name=plugin_name,
                    marketplace=marketplace,
                    root=plugin_dir,
                    enabled=is_enabled,
                    skills=skills,
                    agents=agents,
                    mcp_manifests=mcp,
                )
            )
    return out


def _collect_files(root: Path, filename: str) -> list[FileInfo]:
    """Find all files matching ``filename`` under ``root`` (recursive)."""
    return [FileInfo.from_path(p) for p in root.rglob(filename) if p.is_file()]


def _collect_files_in_subdir(root: Path, subdir: str, *, suffix: str) -> list[FileInfo]:
    target = root / subdir
    if not target.is_dir():
        return []
    return [FileInfo.from_path(p) for p in target.rglob(f"*{suffix}") if p.is_file()]


def _collect_agent_files(root: Path) -> list[FileInfo]:
    """Find all agent .md files under any 'agents/' directory at any depth."""
    out: list[FileInfo] = []
    for p in root.rglob("*.md"):
        if p.is_file() and p.parent.name == "agents":
            out.append(FileInfo.from_path(p))
    return out


def _scan_memories(paths: ClaudePaths) -> tuple[dict[str, FileInfo], dict[str, list[MemoryFileInfo]]]:
    indexes: dict[str, FileInfo] = {}
    files: dict[str, list[MemoryFileInfo]] = {}
    if not paths.projects_dir.is_dir():
        return indexes, files

    for project_dir in sorted(paths.projects_dir.iterdir()):
        if not project_dir.is_dir():
            continue
        memory_dir = project_dir / "memory"
        if not memory_dir.is_dir():
            continue
        key = project_dir.name

        index_path = memory_dir / "MEMORY.md"
        if index_path.is_file():
            indexes[key] = FileInfo.from_path(index_path)

        memory_list: list[MemoryFileInfo] = []
        for mf in sorted(memory_dir.glob("*.md")):
            if mf.name == "MEMORY.md":
                continue
            memory_list.append(_parse_memory_file(mf))
        if memory_list:
            files[key] = memory_list
    return indexes, files


def _parse_memory_file(path: Path) -> MemoryFileInfo:
    """Best-effort parse of YAML frontmatter without a YAML dep."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return MemoryFileInfo(path=path, tokens=0, description=None, type_=None, body_excerpt="")

    description: str | None = None
    type_: str | None = None
    body = text

    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            frontmatter = text[4:end]
            body = text[end + 5 :]
            for line in frontmatter.splitlines():
                stripped = line.strip()
                if stripped.startswith("description:"):
                    description = stripped.split(":", 1)[1].strip().strip('"').strip("'")
                elif stripped.startswith("type:"):
                    type_ = stripped.split(":", 1)[1].strip().strip('"').strip("'")
                elif stripped.startswith("metadata:"):
                    pass  # nested yaml; check following lines for 'type:'

    return MemoryFileInfo(
        path=path,
        tokens=count_file_tokens(path),
        description=description,
        type_=type_,
        body_excerpt=body[:500],
    )
