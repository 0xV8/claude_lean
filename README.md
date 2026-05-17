<div align="center">

# `claude-lean`

**Get 5× more from your Claude Code token budget.**

*Audit, trim, and switch context profiles per project — without touching Claude Code itself.*

[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](./LICENSE)
[![Status](https://img.shields.io/badge/status-alpha-orange)](#status)

</div>

---

## Why

By default, Claude Code loads **every enabled plugin's metadata into your context on every turn**. For a fresh install with the default plugin set, that's often **500,000+ tokens** of agent descriptions, skill metadata, and MCP preambles — *regardless of whether you ever invoke them*.

The result: shorter conversations before compaction, slower responses, higher cost, and a tax on multi-agent workflows. `claude-lean` makes that hidden cost visible — and gives you four levers to reclaim it.

## The Four Levers

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                   │
│   1. AUDIT     →   See exactly what's eating your context        │
│   2. APPLY     →   Disable what you don't use (with backup)      │
│   3. PROFILE   →   Different active set per project / cwd        │
│   4. RESTORE   →   One command back to any previous state         │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

## Quick Start

```bash
# Install (zero hard dependencies beyond rich, which most setups have)
pipx install claude-lean

# 1. See what's costing you
claude-lean audit

# 2. Apply recommendations interactively (with diff + backup + dry-run safety)
claude-lean apply

# 3. Switch to a focused profile in a specific project
cd ~/my-python-project
claude-lean profile use python-ml

# 4. Undo anything
claude-lean restore --latest
```

## Real Numbers From a Real Setup

A representative audit on a default-everything install:

```
─────────────────────────  claude-lean audit  ─────────────────────────

  Plugins enabled: 20  ·  Skills: 262  ·  Agents: 18
  Estimated system-prompt overhead per turn: 593,122 tokens

  Top contributors (tokens / turn):
    engineering-advanced-skills   129,302   ✓ keep
    engineering-skills            123,232   ✓ keep
    marketing-skills              111,126   ⚠ disable (no marketing work)
    c-level-skills                 68,660   ⚠ disable (no exec work)
    ra-qm-skills                   44,325   ⚠ disable (no regulatory work)

  17 findings · Estimated savings if applied: 298,283 tokens / turn
                                              ≈ 2.0× more headroom
```

With per-project profiles (level 3 above), that 2.0× compounds to **5×+** by loading only the plugins relevant to *that* project's stack.

## How It Works

`claude-lean` is a **standalone Python CLI**, not a Claude Code plugin. It runs outside Claude Code and operates on the plain files in `~/.claude/`. Because it never loads into your prompt context, it costs **zero tokens** per Claude conversation.

```
                ┌─────────────────────────────────┐
                │         claude-lean CLI          │
                │     (runs in your terminal)     │
                └────────────────┬────────────────┘
                                 │ reads / writes
                                 ▼
                ┌─────────────────────────────────┐
                │           ~/.claude/             │
                │  • CLAUDE.md                    │
                │  • settings.json                │
                │  • plugins/cache/               │
                │  • projects/*/memory/           │
                └─────────────────────────────────┘
```

See [docs/how-it-works.md](./docs/how-it-works.md) for the full architecture.

## Safety

- **Every write creates a backup first** to `~/.claude/.claude-lean-backups/{timestamp}/`
- **Dry-run is the default for non-TTY usage** — pipes don't accidentally mutate state
- **`claude-lean restore --latest`** reverts the most recent change in one command
- **`--list` shows every snapshot** you've ever made

See [docs/safety.md](./docs/safety.md) for the full safety model.

## Documentation

| Doc | Purpose |
|---|---|
| **[Getting Started](./docs/getting-started.md)** | First-time setup, install, the audit→apply loop |
| **[How It Works](./docs/how-it-works.md)** | Architecture, the four subsystems, data flow |
| **[Safety](./docs/safety.md)** | Backup, restore, dry-run, what we never touch |
| **[FAQ](./docs/faq.md)** | Common questions, troubleshooting, limitations |

## Commands

| Command | What it does |
|---|---|
| `claude-lean audit` | Scan `~/.claude/`, report opportunities (read-only) |
| `claude-lean audit --json` | Machine-readable output |
| `claude-lean apply` | Interactive wizard, applies recommendations with diff + backup |
| `claude-lean apply --dry-run` | Show what would change without writing |
| `claude-lean apply --yes` | Skip interactive prompt (still respects `--dry-run`) |
| `claude-lean profile list` | Show installed profiles |
| `claude-lean profile show <name>` | Print a profile's contents |
| `claude-lean profile use <name>` | Apply a profile (with backup + diff) |
| `claude-lean restore --latest` | Revert the most recent change |
| `claude-lean restore --list` | List all snapshots |

## Status

**v0.1.0 — alpha.** The core (`audit`, `apply`, `restore`, `profile`) is working and tested. The following are roadmapped for later versions:

- **v0.3** — `claude-lean monitor` (live token-usage dashboard from session logs)
- **v0.4** — Claude Code hooks integration (auto-switch profile on `cd`)
- **v1.0** — Profile marketplace + community-contributed profiles

## License

MIT — see [LICENSE](./LICENSE).

## Contributing

Issues and PRs welcome. Per-project profiles are intentionally easy to contribute — drop a TOML file in `src/claude_lean/profile/stock/`, add a test, ship a PR.
