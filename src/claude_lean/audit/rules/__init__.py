"""Rule modules — one anti-pattern detector per file."""

from claude_lean.audit.rules._base import Rule, Finding, Severity
from claude_lean.audit.rules.unused_plugins import UnusedPluginsRule
from claude_lean.audit.rules.forcing_rules import ForcingRulesRule
from claude_lean.audit.rules.stale_memory import StaleMemoryRule
from claude_lean.audit.rules.vague_descriptions import VagueDescriptionsRule
from claude_lean.audit.rules.memory_near_cap import MemoryNearCapRule


def all_rules() -> list[Rule]:
    """Return all built-in rules, in fire order."""
    return [
        UnusedPluginsRule(),
        ForcingRulesRule(),
        StaleMemoryRule(),
        VagueDescriptionsRule(),
        MemoryNearCapRule(),
    ]


__all__ = ["Rule", "Finding", "Severity", "all_rules"]
