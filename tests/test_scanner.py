"""Tests for the scanner."""

from claude_lean.audit.scanner import scan


def test_scan_finds_enabled_plugins(fake_claude_home):
    inv = scan(fake_claude_home)
    assert "engineering-skills@sample-marketplace" in inv.enabled_plugins
    assert "marketing-skills@sample-marketplace" in inv.enabled_plugins
    # disabled plugin should NOT be in enabled list
    assert "ra-qm-skills@sample-marketplace" not in inv.enabled_plugins


def test_scan_finds_skill_files(fake_claude_home):
    inv = scan(fake_claude_home)
    eng = next(p for p in inv.plugins if p.name == "engineering-skills")
    assert len(eng.skills) == 1
    assert eng.skills[0].tokens > 0


def test_scan_finds_agent_files(fake_claude_home):
    inv = scan(fake_claude_home)
    eng = next(p for p in inv.plugins if p.name == "engineering-skills")
    assert len(eng.agents) == 1
    assert eng.agents[0].tokens > 0


def test_scan_finds_memory_files(fake_claude_home):
    inv = scan(fake_claude_home)
    assert "-fake-project" in inv.memory_indexes
    memories = inv.memory_files["-fake-project"]
    names = {m.path.name for m in memories}
    assert names == {"good_memory.md", "vague_memory.md", "stale_memory.md"}


def test_scan_parses_memory_description(fake_claude_home):
    inv = scan(fake_claude_home)
    memories = {m.path.name: m for m in inv.memory_files["-fake-project"]}
    assert memories["good_memory.md"].description is not None
    assert "well-specified" in memories["good_memory.md"].description


def test_scan_loads_claude_md_tokens(fake_claude_home):
    inv = scan(fake_claude_home)
    assert inv.claude_md_path is not None
    assert inv.claude_md_tokens > 0


def test_scan_estimated_total_includes_all_sources(fake_claude_home):
    inv = scan(fake_claude_home)
    expected = (
        inv.total_skill_tokens
        + inv.total_agent_tokens
        + inv.total_mcp_tokens
        + inv.claude_md_tokens
    )
    assert inv.estimated_system_prompt_tokens == expected
