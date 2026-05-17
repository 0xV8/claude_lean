# How It Works

This document covers the architecture of `claude-lean` — how it fits into the Claude Code ecosystem, what its four subsystems do, and how data flows through them.

## Where It Lives

`claude-lean` is a **standalone CLI**, not a Claude Code plugin. It runs in your terminal, reads/writes plain files in `~/.claude/`, and never loads itself into Claude's context.

```
┌──────────────────────────────────────────────────────────────────────┐
│                                                                       │
│   USER TERMINAL                                                       │
│                                                                       │
│         $ claude-lean audit                                          │
│         $ claude-lean apply                                          │
│         $ claude-lean profile use python-ml                          │
│                                                                       │
└────────────────────────────────┬─────────────────────────────────────┘
                                 │
                                 │ reads / writes
                                 ▼
┌──────────────────────────────────────────────────────────────────────┐
│                                                                       │
│   ~/.claude/                                                          │
│                                                                       │
│   ├── CLAUDE.md                  ← rewrites (with backup)           │
│   ├── settings.json              ← rewrites (with backup)           │
│   ├── settings.local.json        ← never modified                    │
│   ├── .claude-lean-backups/      ← our snapshots live here          │
│   │     └── 2026-05-17T08-42Z/                                       │
│   │           ├── CLAUDE.md      ← backup of pre-change file        │
│   │           ├── settings.json                                      │
│   │           └── manifest.json  ← what's in this snapshot          │
│   │                                                                  │
│   ├── plugins/cache/             ← read only (never modified)       │
│   └── projects/*/memory/         ← read only (memory hygiene only)  │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
                                 │
                                 │ Claude Code reads these
                                 ▼
┌──────────────────────────────────────────────────────────────────────┐
│                                                                       │
│   CLAUDE CODE (the `claude` CLI)                                      │
│                                                                       │
│   loads CLAUDE.md + settings.json + enabled plugins                  │
│   into context for every turn                                        │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

Because `claude-lean` runs *outside* Claude Code, it costs **zero** tokens during Claude conversations. The optimization is entirely a build-time effect on your config files.

## The Four Subsystems

```
                  ┌──────────────────────────────────────┐
                  │            claude-lean CLI            │
                  │   (single entry, subcommand routing) │
                  └────────────────┬─────────────────────┘
                                   │
        ┌─────────────────┬────────┴─────────┬──────────────────┐
        ▼                 ▼                  ▼                  ▼
  ┌──────────┐     ┌─────────────┐    ┌──────────────┐    ┌──────────┐
  │  AUDIT   │     │   APPLY     │    │   PROFILE    │    │ RESTORE  │
  │  (read)  │     │  (write)    │    │   (swap)     │    │  (undo)  │
  └──────────┘     └─────────────┘    └──────────────┘    └──────────┘
        │                 │                  │                  │
        └─────────────────┴───────┬──────────┴──────────────────┘
                                  ▼
                       ┌──────────────────────┐
                       │      common/         │
                       │  - claude_paths      │
                       │  - tokenizer         │
                       │  - backup            │
                       │  - log               │
                       └──────────────────────┘
```

### 1. Audit

**Purpose:** Read-only diagnostic. Produces a per-plugin token cost report + a list of detected anti-patterns.

**Data flow:**

```
scan()          analyze()        render()
  │                │                │
  ▼                ▼                ▼
Inventory  →   AuditResult   →   terminal output / JSON
```

**Scanner** walks `~/.claude/`:
- `CLAUDE.md` → counted
- `settings.json` → parsed for `enabledPlugins`
- `plugins/cache/{marketplace}/{plugin}/**/SKILL.md` → discovered + counted
- `plugins/cache/{marketplace}/{plugin}/**/agents/*.md` → discovered + counted
- `plugins/cache/{marketplace}/{plugin}/**/mcp.json` → discovered + counted
- `projects/{encoded}/memory/MEMORY.md` → counted
- `projects/{encoded}/memory/*.md` → parsed (frontmatter + body excerpt)

**Analyzer** runs a list of `Rule` objects over the inventory. v0.1 ships five:

| Rule | Detects |
|---|---|
| `unused-plugins` | Plugin packs that don't match engineering work (marketing, c-level, finance, regulatory, etc.) |
| `forcing-rules-in-claude-md` | "Always use agents" style rules that cause expensive sub-agent spawns |
| `stale-memory-snapshot` | Memory bodies with `as of YYYY-MM-DD` markers older than 30 days |
| `vague-memory-description` | Memory descriptions shorter than 60 chars or containing generic words |
| `memory-index-near-cap` | `MEMORY.md` files within 20 lines of the 200-line truncation cap |

Each rule emits zero or more `Finding` objects with severity, evidence, and (where applicable) an estimated token savings.

### 2. Apply

**Purpose:** Take an audit result and an interactive wizard's input; produce an optimized `CLAUDE.md` + `settings.json`; write them with a backup.

**Data flow:**

```
wizard         build_plan         show_diff         (confirm)
  │                │                  │                 │
  ▼                ▼                  ▼                 ▼
WizardResult → GeneratorPlan → terminal diff → snapshot → write
                                                  │
                                                  ▼
                                       ~/.claude/.claude-lean-backups/...
```

**Wizard** asks the user 4 questions about their stack and preferences. **Generator** uses those answers to:
- Compute a new `enabledPlugins` dict (keeps core eng plugins, disables stack-irrelevant ones)
- Rewrite `CLAUDE.md` (drop forcing rules, optionally add stack hints)

The user always sees a **diff** before anything is written. A snapshot is made *before* the write so `restore` can put everything back.

### 3. Profile

**Purpose:** Swap entire context configurations per project.

**Profile schema** (TOML):

```toml
schema_version = 1
name = "python-ml"
display_name = "Python ML / AI"
description = "Python ML/AI work on macOS, MLX-first."
version = "1.0.0"
target_stack = ["python", "mlx", "macos"]

[plugins.enabled]
plugins = ["engineering-skills", "superpowers", ...]

[plugins.disabled]
plugins = ["marketing-skills", "ra-qm-skills", ...]

[claude_md]
mode = "replace"   # or "append" / "prepend"
content = """
- Default to Python 3.14 unless project requires older
- Prefer MLX over PyTorch on Apple Silicon
...
"""
```

**Subcommands:**
- `profile list` — show installed stock profiles
- `profile show <name>` — print a profile's TOML
- `profile use <name>` — apply a profile (with backup + diff)

Stock profiles ship with the package: `python-ml`, `frontend-web`, `minimal`. Custom profiles can be authored as TOML files.

### 4. Restore

**Purpose:** Revert any change `claude-lean` ever made.

Every write that mutates `~/.claude/` first creates a snapshot under `~/.claude/.claude-lean-backups/{ISO-timestamp}/`. Each snapshot has a `manifest.json` recording which files it covers.

```bash
claude-lean restore --list           # show all snapshots
claude-lean restore --latest         # restore the most recent
claude-lean restore --snapshot NAME  # restore a specific one
```

## The Tokenizer

Two modes:

- **Exact** — if `tiktoken` is installed, we use `cl100k_base` (Anthropic-family tokenizer). Counts match what Claude actually sees, to within a few percent.
- **Approximate** — falls back to byte-based estimation (1 token ≈ 4 bytes for English/code). Within ~15% for typical content.

The approximation is intentional: most users don't have `tiktoken` installed, and forcing a heavy install (BPE data is ~50MB) defeats the "lean" purpose. The approximation is good enough for ranking — the *order* of plugins by cost is identical between modes, even if the absolute numbers differ.

For exact counts:

```bash
pipx install 'claude-lean[accurate]'   # adds tiktoken
```

## Audit Output Schema

`claude-lean audit --json` produces a stable JSON document:

```json
{
  "schema_version": 1,
  "generated_at": "2026-05-17T08:42:00Z",
  "claude_home": "/Users/you/.claude",
  "tokenizer_accuracy": "exact (tiktoken)",
  "totals": {
    "plugins_enabled": 20,
    "plugins_installed": 20,
    "skills_loaded": 262,
    "agents_loaded": 18,
    "estimated_system_prompt_tokens": 593122,
    "claude_md_tokens": 50
  },
  "by_plugin": [
    {
      "name": "engineering-advanced-skills",
      "marketplace": "claude-code-skills",
      "enabled": true,
      "tokens_skills": 123737,
      "tokens_agents": 5565,
      "tokens_mcp": 0,
      "tokens_total": 129302
    }
  ],
  "findings": [
    {
      "rule_id": "unused-plugins",
      "severity": "warn",
      "title": "'marketing-skills' likely unused in engineering workflows",
      "evidence": "...",
      "suggested_action": "...",
      "estimated_savings_tokens": 111126,
      "target": "marketing-skills",
      "metadata": { "marketplace": "claude-code-skills" }
    }
  ],
  "recommendations_summary": {
    "estimated_tokens_saved_per_turn": 298283,
    "estimated_multiplier_gain": 2.0
  }
}
```

## File Layout (Inside the Package)

```
claude_lean/
├── cli.py                   # argparse + subcommand routing
├── common/
│   ├── claude_paths.py      # locate ~/.claude/
│   ├── tokenizer.py         # exact (tiktoken) + fallback
│   ├── backup.py            # snapshot/restore
│   └── log.py
├── audit/
│   ├── scanner.py           # walks ~/.claude/, builds Inventory
│   ├── analyzer.py          # runs Rules over Inventory
│   ├── report.py            # rich terminal + JSON renderers
│   └── rules/               # one anti-pattern per file
├── apply/
│   ├── wizard.py            # interactive Q&A
│   ├── generator.py         # produces optimized config
│   └── memory_cleaner.py    # strips stale snapshot sections
└── profile/
    ├── schema.py            # Profile dataclass + TOML loader
    ├── manager.py           # list / get / apply
    └── stock/               # bundled profiles
        ├── python-ml.toml
        ├── frontend-web.toml
        └── minimal.toml
```

## What `claude-lean` Will Never Do

- Modify Claude Code internals
- Make network calls (except `profile install` from a marketplace, which is opt-in)
- Send telemetry off your machine
- Touch `settings.local.json` (that's your local-only overrides)
- Edit `MEMORY.md` content automatically (memory hygiene rules *report* — the user fixes manually for now)
- Run without showing you a diff first when writing
