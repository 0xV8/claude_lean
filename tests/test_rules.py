"""Tests for the rules engine."""

from claude_lean.audit.scanner import scan
from claude_lean.audit.analyzer import analyze
from claude_lean.audit.rules import (
    UnusedPluginsRule,
    ForcingRulesRule,
    StaleMemoryRule,
    VagueDescriptionsRule,
    MemoryNearCapRule,
)


def test_unused_plugins_rule_fires_on_marketing(fake_claude_home):
    inv = scan(fake_claude_home)
    findings = UnusedPluginsRule().evaluate(inv)
    targets = {f.target for f in findings}
    assert "marketing-skills" in targets
    # engineering-skills is enabled but NOT in the unused list
    assert "engineering-skills" not in targets


def test_unused_plugins_rule_estimates_savings(fake_claude_home):
    inv = scan(fake_claude_home)
    findings = UnusedPluginsRule().evaluate(inv)
    for f in findings:
        assert f.estimated_savings_tokens > 0


def test_forcing_rules_fires_on_always_use_agents(fake_claude_home):
    inv = scan(fake_claude_home)
    findings = ForcingRulesRule().evaluate(inv)
    assert len(findings) >= 1
    assert any("always" in f.evidence.lower() for f in findings)


def test_vague_descriptions_fires_on_short_description(fake_claude_home):
    inv = scan(fake_claude_home)
    findings = VagueDescriptionsRule().evaluate(inv)
    targets = {f.target for f in findings}
    # vague_memory.md has description "notes" → should fire
    assert any("vague_memory" in t for t in targets)
    # good_memory.md has a long detailed description → should NOT fire
    assert not any("good_memory" in t for t in targets)


def test_stale_memory_fires_on_old_snapshot(fake_claude_home):
    inv = scan(fake_claude_home)
    findings = StaleMemoryRule().evaluate(inv)
    targets = {f.target for f in findings}
    assert any("stale_memory" in t for t in targets)


def test_memory_near_cap_does_not_fire_on_short_index(fake_claude_home):
    # Fixture's MEMORY.md is only 3 lines; rule should not fire
    inv = scan(fake_claude_home)
    findings = MemoryNearCapRule().evaluate(inv)
    assert findings == []


def test_analyzer_runs_all_rules(fake_claude_home):
    inv = scan(fake_claude_home)
    result = analyze(inv)
    rule_ids = {f.rule_id for f in result.findings}
    # Expect at least these rules to have fired in our fixture
    assert "unused-plugins" in rule_ids
    assert "forcing-rules-in-claude-md" in rule_ids
    assert "vague-memory-description" in rule_ids
    assert "stale-memory-snapshot" in rule_ids


def test_analyzer_multiplier_gain_is_at_least_one(fake_claude_home):
    inv = scan(fake_claude_home)
    result = analyze(inv)
    assert result.multiplier_gain >= 1.0
