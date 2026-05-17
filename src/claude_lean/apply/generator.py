"""Generate optimized settings.json + CLAUDE.md based on wizard input."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from claude_lean.apply.wizard import WizardResult
from claude_lean.audit.rules.unused_plugins import LIKELY_UNUSED_FOR_ENGINEERING
from claude_lean.common.claude_paths import ClaudePaths


# Plugin packs to always keep enabled for engineering work
_CORE_ENG_PLUGINS = {
    "engineering-skills",
    "engineering-advanced-skills",
    "superpowers",
    "context7",
    "github",
    "code-review",
    "feature-dev",
    "code-simplifier",
    "self-improving-agent",
}

# Plugin packs that depend on a specific stack
_STACK_TO_PLUGINS = {
    "frontend": {"frontend-design", "playwright"},
    "javascript/typescript": {"frontend-design", "playwright"},
}

# Non-engineering work areas that need their corresponding plugins
_WORK_TO_PLUGINS = {
    "marketing": {"marketing-skills", "content-creator"},
    "sales": {"business-growth-skills"},
    "finance": {"finance-skills"},
    "product": {"product-skills"},
    "regulatory": {"ra-qm-skills"},
}


@dataclass
class GeneratorPlan:
    """The proposed changes; render to diff before applying."""

    new_settings: dict[str, Any]
    old_settings: dict[str, Any]
    new_claude_md: str
    old_claude_md: str
    plugin_disables: list[str]
    plugin_keeps: list[str]
    settings_path: Path
    claude_md_path: Path

    @property
    def has_changes(self) -> bool:
        return self.new_settings != self.old_settings or self.new_claude_md != self.old_claude_md


def build_plan(paths: ClaudePaths, wizard: WizardResult) -> GeneratorPlan:
    """Build a GeneratorPlan from current state + wizard input."""
    old_settings = _load_json(paths.settings_json)
    new_settings = _optimize_settings(old_settings, wizard)

    old_claude_md = paths.global_claude_md.read_text(encoding="utf-8") if paths.global_claude_md.is_file() else ""
    new_claude_md = _optimize_claude_md(old_claude_md, wizard)

    # Diff plugin states for the human summary
    old_enabled = set(_enabled_keys(old_settings))
    new_enabled = set(_enabled_keys(new_settings))
    disables = sorted(old_enabled - new_enabled)
    keeps = sorted(new_enabled)

    return GeneratorPlan(
        new_settings=new_settings,
        old_settings=old_settings,
        new_claude_md=new_claude_md,
        old_claude_md=old_claude_md,
        plugin_disables=disables,
        plugin_keeps=keeps,
        settings_path=paths.settings_json,
        claude_md_path=paths.global_claude_md,
    )


def write_plan(plan: GeneratorPlan) -> None:
    """Write the plan to disk. Caller is responsible for creating backups first."""
    plan.settings_path.parent.mkdir(parents=True, exist_ok=True)
    plan.settings_path.write_text(json.dumps(plan.new_settings, indent=2) + "\n", encoding="utf-8")
    plan.claude_md_path.parent.mkdir(parents=True, exist_ok=True)
    plan.claude_md_path.write_text(plan.new_claude_md, encoding="utf-8")


# ---- internals ----


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _enabled_keys(settings: dict[str, Any]) -> list[str]:
    raw = settings.get("enabledPlugins", {})
    if not isinstance(raw, dict):
        return []
    return [k for k, v in raw.items() if v]


def _optimize_settings(old: dict[str, Any], wizard: WizardResult) -> dict[str, Any]:
    """Produce a new settings.json keeping the structure but trimming plugins."""
    out = dict(old)  # shallow copy
    plugins = dict(out.get("enabledPlugins", {}))

    # Decide which plugin keys to keep
    needed_plugin_names = set(_CORE_ENG_PLUGINS)
    for stack in wizard.primary_stacks:
        needed_plugin_names.update(_STACK_TO_PLUGINS.get(stack, set()))
    for work in wizard.non_eng_work:
        needed_plugin_names.update(_WORK_TO_PLUGINS.get(work, set()))

    aggressive = wizard.aggressiveness == "aggressive"
    conservative = wizard.aggressiveness == "conservative"

    for key in list(plugins.keys()):
        plugin_name = key.split("@", 1)[0]
        if plugin_name in needed_plugin_names:
            plugins[key] = True
            continue
        if plugin_name in LIKELY_UNUSED_FOR_ENGINEERING and not conservative:
            plugins[key] = False
            continue
        if aggressive and plugin_name not in _CORE_ENG_PLUGINS:
            plugins[key] = False
            continue
        # Otherwise leave as-is

    out["enabledPlugins"] = plugins
    return out


def _optimize_claude_md(old: str, wizard: WizardResult) -> str:
    """Rewrite CLAUDE.md to remove forcing rules and add stack hints."""
    lines = old.splitlines()
    cleaned: list[str] = []

    for line in lines:
        stripped = line.strip().lower()
        # Drop "always use all agents" and similar forcing rules
        if "always use" in stripped and "agent" in stripped:
            cleaned.append(
                "- Use agents when work is specialized or parallelizable, "
                "not for simple edits"
            )
            continue
        if "always use all" in stripped:
            continue  # filtered out
        cleaned.append(line)

    # Add a stack-aware hint if not already present
    stack_hint = _stack_hint(wizard.primary_stacks)
    if stack_hint and stack_hint not in "\n".join(cleaned):
        cleaned.append(stack_hint)

    # Trailing newline discipline
    text = "\n".join(cleaned).rstrip() + "\n"
    return text


def _stack_hint(stacks: list[str]) -> str | None:
    if "python" in stacks and "ml/ai" in stacks:
        return "- Prefer MLX over PyTorch for local ML on Apple Silicon when possible"
    if "rust" in stacks:
        return "- Default to safe Rust; only reach for unsafe when measurably necessary"
    return None
