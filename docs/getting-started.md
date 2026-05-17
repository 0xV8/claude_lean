# Getting Started

This walks you from "I just heard about claude-lean" to "my Claude Code conversations cost 2-5× less."

## 1. Install

`claude-lean` needs **Python 3.11 or newer**. Install via `pipx` (recommended — isolates the tool from your other Python work):

```bash
pipx install claude-lean
```

Or via `pip`:

```bash
pip install claude-lean
```

The only hard dependency is `rich` (for the terminal output). For exact (rather than approximate) token counts, install with the `accurate` extra:

```bash
pipx install 'claude-lean[accurate]'   # adds tiktoken
```

Verify:

```bash
$ claude-lean --version
claude-lean 0.1.0
```

## 2. Your First Audit

Run a read-only audit. **Nothing on your disk changes.**

```bash
claude-lean audit
```

You'll see something like:

```
─────────────────── claude-lean audit · /Users/you/.claude ───────────────────
Token measurement: approximate (byte-based)

  Plugins enabled: 20  ·  Skills: 262  ·  Agents: 18
  Estimated system-prompt overhead per turn: 593,122 tokens

  ┌─────────────────────────────┬─────────┬───────┬──────────────┐
  │ Plugin                      │ Skills  │ Agents│ Total tokens │
  ├─────────────────────────────┼─────────┼───────┼──────────────┤
  │ engineering-advanced-skills │ 123,737 │ 5,565 │ 129,302      │
  │ engineering-skills          │ 119,327 │ 3,905 │ 123,232      │
  │ marketing-skills            │ 111,126 │     0 │ 111,126      │
  │ c-level-skills              │  67,260 │ 1,400 │  68,660      │
  │ ra-qm-skills                │  44,325 │     0 │  44,325      │
  └─────────────────────────────┴─────────┴───────┴──────────────┘

Findings: 0 critical · 17 warn · 0 info

⚠ unused-plugins (8)
    'marketing-skills' likely unused in engineering workflows
    → est. savings: 111,126 tokens/turn
    [... 7 more ...]

⚠ forcing-rules-in-claude-md (1)
    Forcing rule on line 1 of CLAUDE.md
    "Always use all agents"

⚠ vague-memory-description (9)
    [... 9 memory files with descriptions too vague for retrieval ...]

  Estimated tokens saved per turn if applied: 298,283 tokens
                                              ≈ 2.0× more headroom

  Next: run `claude-lean apply` to act on these recommendations.
```

### What Each Finding Means

| Finding | What it's saying | What to do |
|---|---|---|
| `unused-plugins` | These plugin packs are enabled but their content area (marketing, finance, etc.) doesn't match engineering work | Disable in `settings.json` — `apply` does this for you |
| `forcing-rules-in-claude-md` | Your CLAUDE.md has a rule that forces sub-agent spawning even for trivial work | Rewrite the rule to be conditional — `apply` proposes a replacement |
| `stale-memory-snapshot` | A memory file contains dated state (e.g., "as of 2026-04-30") that's likely no longer accurate | Move the snapshot to a project README; keep policy in memory |
| `vague-memory-description` | A memory's description in `MEMORY.md` is too vague — Claude won't pull the memory body in | Rewrite the description to mention the topic/constraint |
| `memory-index-near-cap` | `MEMORY.md` is approaching the 200-line truncation cap | Consolidate or sharpen entries |

## 3. Apply Recommendations (Safely)

Now act on what the audit found. The simplest path is a **dry-run first**:

```bash
claude-lean apply --dry-run --yes
```

This shows exactly what would change — a diff of `CLAUDE.md` and the list of plugins to be disabled — **without writing anything**.

When you're happy, run interactively:

```bash
claude-lean apply
```

You'll be asked four short questions:

1. **What's your primary stack?** (Python, JS/TS, Rust, Go, ML/AI, DevOps, Frontend, Mobile, Other)
2. **Any non-engineering work types?** (Marketing, Sales, Finance, Product, Regulatory, None)
3. **How aggressive?** (conservative / balanced / aggressive)
4. **Apply now?** (you'll see the diff before this)

A backup is written to `~/.claude/.claude-lean-backups/{timestamp}/` *before* anything is changed. You can revert instantly:

```bash
claude-lean restore --latest
```

## 4. Per-Project Profiles

The biggest wins come from **different active plugin sets per project**. List the stock profiles:

```bash
$ claude-lean profile list
Stock profiles:
  frontend-web — React/Vue/Svelte + TypeScript frontend work with browser automation.
  minimal — Tightest engineering profile: core deps only, no specialized packs.
  python-ml — Python ML/AI work on macOS, MLX-first, stdlib-heavy.
```

Switch to one in the project's directory:

```bash
$ cd ~/projects/my-tts-app
$ claude-lean profile use python-ml
```

You'll get a diff preview and a backup before anything is written.

To revert:

```bash
claude-lean restore --latest
# Or to any specific snapshot:
claude-lean restore --list                  # see all snapshots
claude-lean restore --snapshot <name>
```

## 5. JSON Mode (for CI / scripts)

Every command supports machine-readable output:

```bash
claude-lean audit --json > audit.json
claude-lean audit --json-out audit.json
```

The JSON schema is documented in [how-it-works.md](./how-it-works.md#audit-output-schema).

## Next Steps

- Read [how-it-works.md](./how-it-works.md) to understand the architecture
- Read [safety.md](./safety.md) for the full backup / restore model
- Read [faq.md](./faq.md) for known limitations and troubleshooting
- Contribute a profile to the marketplace (PRs welcome)
