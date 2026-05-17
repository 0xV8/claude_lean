# claude-lean — Design Spec

**Status:** Draft v1
**Date:** 2026-05-16
**Author:** vipin (contact@buffercode.in)
**Type:** Greenfield project design — open-source tool
**Target version:** v0.1.0 (minimum shippable) through v1.0.0

---

## 1. Problem Statement

Claude Code users — especially those who enable a generous default plugin set — pay a large, hidden, per-turn token cost for context they never use. A representative default-everything install can spend **50–80k tokens per turn** on system prompt overhead alone: sub-agent descriptions, skill metadata, MCP preambles, and forcing-rule CLAUDE.md content. This:

- **Reduces effective conversation length** before context compaction kicks in
- **Slows responses** (more tokens to encode, larger cache invalidations)
- **Costs more** on metered plans
- **Compounds in multi-agent workflows** — each spawned sub-agent inherits a similar overhead
- **Penalizes users equally** regardless of whether they ever invoke the loaded plugins

The hidden nature of the cost is the core issue. Users don't see what's eating their context, so they can't act on it.

## 2. Goals

| # | Goal | Measurement |
|---|---|---|
| G1 | **5× more useful work per token** for a default-everything user who applies the tool's recommendations | System prompt token reduction ≥ 80% on baseline → measured via `tiktoken` |
| G2 | **Make the hidden visible** | Every plugin, agent, skill, and CLAUDE.md line gets a token cost in the audit output |
| G3 | **Reversible by default** | Every change is `--dry-run` first, with a backup of originals; restore is one command |
| G4 | **Open-source, community-extensible** | MIT license, profile marketplace, profile contributions via PR |
| G5 | **Feed back to Anthropic** | Reproducible measurement scripts produce data Anthropic engineers can act on |

## 3. Non-Goals

- ❌ Not a fork or wrapper around `claude` CLI
- ❌ Does not modify Claude Code internals or call Anthropic APIs
- ❌ Not a prompt engineer / context optimizer at conversation time — it operates on **config artifacts**, not live prompts
- ❌ Does not ship its own LLM or do client-side tokenization for *every* conversation; only for static config files
- ❌ Not a replacement for `MEMORY.md` / `CLAUDE.md` — it cleans them up, doesn't supplant them
- ❌ No telemetry sent off the user's machine (privacy by design)

---

## 4. The 5× Claim — Justification

Baseline: a default-everything user with all standard plugin packs enabled. Estimated system prompt overhead ≈ 60k tokens per turn.

| Step | Mechanism | Reduction | Cumulative multiplier |
|---|---|---:|---:|
| 0 | Default everything | — | 1.0× |
| 1 | Plugin trim (disable 7–10 unused plugin packs) | ~45% | 1.8× |
| 2 | CLAUDE.md rewrite (drop forcing-rules, fix bloat) | ~10% | 2.0× |
| 3 | Memory hygiene (remove stale snapshots, sharpen descriptions) | ~5% | 2.1× |
| 4 | `settings.json` permission allowlist (fewer re-prompts) | ~8% | 2.3× |
| 5 | **Profile switching** (different active set per cwd) | ~35% | 3.5× |
| 6 | Hook-driven auto-activation (profile changes on `cd` without manual command) | ~25% | 4.7× |
| 7 | Conversation/memory archival (auto-clean unused conversations) | ~5% | **~5.0×** |

**Why steps 1 and 5 both work, despite both involving plugin trimming:**
- Step 1 is *global*: disables plugins the user *never* uses (e.g., `marketing-skills` for an engineer)
- Step 5 is *per-cwd*: even within "plugins the user uses sometimes," only the relevant subset loads in any given project (e.g., `frontend-design` plugin loaded only when in a JS project; not loaded when working on Python ML)
- Step 6 makes step 5 *automatic* — no manual `profile use` per `cd`

Steps 1–4 land with `audit` + `apply` (v0.1.0–v0.2.0). Steps 5–7 land with profiles + hooks (v0.3.0–v0.4.0). The 5× claim is a v1.0 promise, with intermediate versions delivering 2.3× → 3.5× → 4.7× along the way.

All numbers in §4 are estimates derived from a sample audit of a representative `~/.claude/`. They become measured numbers in the audit-output appendix once `audit` is implemented and run against real installs.

---

## 5. Architecture Overview

```
                 ┌──────────────────────────────────────────────┐
                 │            claude-lean CLI                   │
                 │   (single entry point, subcommand routing)   │
                 └────────────────────┬─────────────────────────┘
                                      │
        ┌─────────────────┬───────────┴────────────┬──────────────────┐
        ▼                 ▼                        ▼                  ▼
  ┌──────────┐     ┌─────────────┐         ┌──────────────┐     ┌──────────┐
  │  AUDIT   │     │   APPLY     │         │   PROFILE    │     │ MONITOR  │
  │  (read)  │     │  (write)    │         │   (swap)     │     │  (tail)  │
  └──────────┘     └─────────────┘         └──────────────┘     └──────────┘
        │                 │                        │                  │
        └─────────────────┴─────────┬──────────────┴──────────────────┘
                                    ▼
                       ┌──────────────────────────┐
                       │      common/             │
                       │  - claude_paths          │
                       │  - tokenizer (tiktoken)  │
                       │  - config models         │
                       │  - backup/restore        │
                       └──────────────────────────┘
                                    │
                                    ▼
                       ┌──────────────────────────┐
                       │    ~/.claude/  (user's   │
                       │     Claude Code config)  │
                       └──────────────────────────┘
```

### Principles

- **Each layer is a self-contained subcommand** that can be invoked independently and tested in isolation
- **Read paths never modify**; write paths require explicit `--apply` flag (default is dry-run)
- **All writes go through `common/backup`**, which copies originals to `~/.claude/.claude-lean-backups/{timestamp}/` before any change
- **All token measurements use `tiktoken` with `cl100k_base` encoding** (Anthropic-family tokenizer)
- **Profiles are pure data** (TOML files) — code interprets them; no executable code in a profile

---

## 6. Module Layout

```
claude-lean/
├── pyproject.toml
├── README.md
├── LICENSE                          # MIT
├── docs/
│   ├── superpowers/specs/           # this file + future specs
│   ├── user-guide.md
│   ├── profile-authoring.md
│   └── architecture.md
├── research/
│   └── claude-token-economy.md      # the research paper (v1.0)
├── src/
│   └── claude_lean/
│       ├── __init__.py
│       ├── __main__.py              # `python -m claude_lean`
│       ├── cli.py                   # argparse routing
│       ├── common/
│       │   ├── claude_paths.py      # locate ~/.claude/, projects/, plugins/
│       │   ├── tokenizer.py         # tiktoken wrapper, byte→token estimates
│       │   ├── backup.py            # snapshot ~/.claude/ before changes
│       │   ├── config_models.py     # typed dataclasses for settings.json etc.
│       │   └── log.py               # structured logging
│       ├── audit/
│       │   ├── __init__.py
│       │   ├── scanner.py           # walks plugin cache + memory dir
│       │   ├── analyzer.py          # rules engine for anti-patterns
│       │   ├── report.py            # rich + JSON renderers
│       │   └── rules/               # individual rule modules (one per anti-pattern)
│       │       ├── unused_plugins.py
│       │       ├── forcing_rules.py
│       │       ├── stale_memory.py
│       │       └── verbose_descriptions.py
│       ├── apply/
│       │   ├── __init__.py
│       │   ├── wizard.py            # interactive Q&A (questionary-free, stdlib)
│       │   ├── generator.py         # produces optimized settings + CLAUDE.md
│       │   └── memory_cleaner.py    # prunes stale memory entries
│       ├── profile/
│       │   ├── __init__.py
│       │   ├── schema.py            # Profile dataclass + TOML validation
│       │   ├── manager.py           # install / use / restore / list
│       │   ├── stock/               # bundled profiles
│       │   │   ├── python-ml.toml
│       │   │   ├── frontend-web.toml
│       │   │   ├── data-engineering.toml
│       │   │   ├── devops.toml
│       │   │   └── minimal.toml
│       │   └── marketplace.py       # fetch from claude-lean-profiles repo
│       └── monitor/
│           ├── __init__.py
│           ├── log_reader.py        # parses ~/.claude/projects/*/session.jsonl
│           ├── trends.py            # rolling stats, by-tool/by-agent breakdown
│           └── tui.py               # text-mode dashboard
└── tests/
    ├── fixtures/
    │   └── fake_claude_home/        # synthetic ~/.claude/ for tests
    ├── test_scanner.py
    ├── test_tokenizer.py
    ├── test_analyzer.py
    ├── test_profile_roundtrip.py
    ├── test_apply_dry_run.py
    └── test_cli.py
```

Total estimated code: **~2,500–3,500 LOC** for v1.0.

---

## 7. Layer Specifications

### 7.1 Layer 1 — `claude-lean audit`

**Purpose:** Read-only diagnostic. Produces a per-plugin and per-anti-pattern report with measured token costs and actionable recommendations.

**Inputs:**
- `~/.claude/CLAUDE.md`
- `~/.claude/settings.json` and `settings.local.json`
- `~/.claude/plugins/cache/**/SKILL.md`
- `~/.claude/plugins/cache/**/agents/*.md`
- `~/.claude/plugins/cache/**/mcp.json` (or equivalent manifest)
- `~/.claude/projects/{cwd-encoded}/memory/MEMORY.md` and individual memory files
- (Optional, for `--with-usage`) `~/.claude/projects/*/session-*.jsonl`

**Outputs:**
- Terminal report (human-friendly, color, tables) via stdout
- JSON report (`--json` or `--json-out path`) for machine consumption
- Exit code: `0` if no critical issues, `1` if any rule fires at `critical` severity

**Anti-pattern rules (v0.1.0):**

| Rule | Severity | Detection |
|---|---|---|
| `unused-plugins` | warn | Plugin's skills/agents never appear in any session log AND don't match declared user stack |
| `forcing-rules-in-claude-md` | warn | CLAUDE.md contains "always", "must", "every time" + "agent" or "tool" |
| `stale-memory-snapshot` | warn | Memory file body contains absolute paths, version numbers, or "(as of YYYY-MM-DD)" markers older than 30 days |
| `vague-memory-description` | warn | MEMORY.md line description < 60 chars OR matches generic keywords (`notes`, `stuff`, `info`) |
| `verbose-agent-examples` | info | Agent file > 200 lines |
| `duplicate-memories` | warn | Two memories have similarity > 0.8 (Jaccard on tokens) |
| `permissions-not-configured` | info | `settings.json` lacks `permissions` block |
| `memory-index-near-cap` | warn | MEMORY.md > 180 lines |

**Algorithm sketch:**
```python
def audit(claude_home: Path) -> AuditReport:
    inventory = scanner.scan(claude_home)             # all files + sizes
    token_costs = tokenizer.count_all(inventory)      # tiktoken on each
    findings = []
    for rule in load_rules():
        findings.extend(rule.evaluate(inventory, token_costs))
    return AuditReport(inventory, token_costs, findings)
```

**Output schema (JSON):**
```json
{
  "schema_version": 1,
  "generated_at": "2026-05-16T22:33:00Z",
  "claude_home": "/Users/vipin/.claude",
  "totals": {
    "plugins_enabled": 20,
    "skills_loaded": 262,
    "agents_loaded": 49,
    "estimated_system_prompt_tokens": 58234
  },
  "by_plugin": [
    {
      "name": "engineering-skills",
      "enabled": true,
      "tokens_skills": 4234,
      "tokens_agents": 8901,
      "tokens_mcp": 412,
      "tokens_total": 13547,
      "usage_last_30_days": 47,
      "verdict": "keep"
    }
  ],
  "findings": [
    {
      "rule": "unused-plugins",
      "severity": "warn",
      "plugin": "marketing-skills",
      "evidence": "no skill or agent invocations in last 30 days",
      "estimated_savings_tokens": 2810,
      "suggested_action": "disable in settings.json"
    }
  ],
  "recommendations_summary": {
    "estimated_tokens_saved_per_turn": 22310,
    "estimated_multiplier_gain": "2.4x"
  }
}
```

### 7.2 Layer 2 — `claude-lean apply`

**Purpose:** Write recommended changes from an audit report to `~/.claude/`. Always backs up originals; always shows a diff before writing.

**Modes:**
- `claude-lean apply` — interactive wizard
- `claude-lean apply --from audit.json` — use a previously-generated audit report
- `claude-lean apply --auto` — accept all `safe`-tier recommendations without prompting
- `claude-lean apply --dry-run` — print diffs, write nothing (default behaviour when stdout is not a TTY)

**Wizard questions (v0.1.0):**
1. What's your primary stack? (multi-select: python, js/ts, rust, go, ml/ai, devops, frontend, mobile, other)
2. Do you do any of these non-engineering work types? (multi-select: marketing, sales, finance, product, regulatory, none)
3. How aggressive should we be? (conservative / balanced / aggressive)
4. Apply changes now, or just write recommendations to a file? (apply / save-only)

Each question maps to a set of plugin-keep / plugin-disable decisions. The wizard maps answers → a generated `settings.json` + `CLAUDE.md` template; user reviews diff; confirms write.

**Backup strategy:**
- Before any write, snapshot affected files to `~/.claude/.claude-lean-backups/{ISO-timestamp}/`
- `claude-lean restore --latest` reverts the most recent change set
- `claude-lean restore --list` shows available snapshots

### 7.3 Layer 3 — `claude-lean profile`

**Purpose:** Swap entire context profiles per project. The most novel and highest-impact feature.

**Subcommands:**
| Command | Effect |
|---|---|
| `claude-lean profile list` | Show installed profiles |
| `claude-lean profile show <name>` | Print profile contents |
| `claude-lean profile use <name>` | Apply profile to current `~/.claude/` (backs up first) |
| `claude-lean profile use <name> --cwd <path>` | Apply only when in that directory (via `.claude-lean` marker file) |
| `claude-lean profile restore` | Revert to previous profile |
| `claude-lean profile create <name>` | Snapshot current `~/.claude/` as a new local profile |
| `claude-lean profile install <name-or-url>` | Fetch from marketplace |
| `claude-lean profile publish` | Open a marketplace PR (v0.4.0+) |

**Application model:**
- A profile defines: `enabled_plugins`, optional `claude_md` body, optional `settings_overlay`
- `profile use` performs: (1) snapshot current `~/.claude/CLAUDE.md` + `settings.json`, (2) overlay the profile's values, (3) write new files
- Per-cwd profiles: drop a `.claude-lean` file containing the profile name in a project root → a hook (v0.4.0) auto-applies on `cd` (until then, manual `profile use` per project)

### 7.4 Layer 4 — `claude-lean monitor`

**Purpose:** Show real per-turn token consumption from actual session logs, not just static config estimates. Validates the savings claim with real data.

**Subcommands:**
| Command | Effect |
|---|---|
| `claude-lean monitor` | TUI dashboard, live tailing the most-recent session |
| `claude-lean monitor --project <path>` | Filter to one project |
| `claude-lean monitor report --since 7d` | Static report of last 7 days |
| `claude-lean monitor export --json` | Raw per-turn data for further analysis |

**Data points surfaced:**
- Per-turn input token count (parsed from session log)
- Per-tool-call output size
- Sub-agent count per turn (multi-agent overhead indicator)
- Cache-hit ratio (proxied from response latency / size)
- Drift over time (is the average prompt growing?)

---

## 8. Profile Format

Profiles are TOML files. Validated against a schema (in `profile/schema.py`).

```toml
# Example: src/claude_lean/profile/stock/python-ml.toml

schema_version = 1
name = "python-ml"
display_name = "Python ML / AI"
description = "Python ML/AI work on macOS, MLX-first, stdlib-heavy"
version = "1.0.0"
author = "claude-lean stock profiles"
target_stack = ["python", "mlx", "pytorch", "huggingface", "macos"]
recommended_for = ["TTS work", "local model fine-tuning", "data science"]

[plugins.enabled]
plugins = [
  "engineering-skills",
  "engineering-advanced-skills",
  "superpowers",
  "context7",
  "github",
  "code-review",
  "feature-dev",
  "code-simplifier",
  "self-improving-agent",
]

[plugins.disabled]
plugins = [
  "marketing-skills",
  "c-level-skills",
  "ra-qm-skills",
  "business-growth-skills",
  "finance-skills",
  "pm-skills",
  "content-creator",
  "frontend-design",
  "playwright",
  "product-skills",
]

[claude_md]
mode = "replace"   # or "append" / "prepend"
content = """
- Default to Python 3.14 unless project requires older
- Prefer MLX over PyTorch for local ML; far less RAM on Apple Silicon
- Use stdlib-only when possible; minimize deps
- Use agents when work is specialized or parallelizable, not for simple edits
- When you create commits, releases, or code, don't add credit attribution
"""

[settings_overlay]
# Keys are flattened dotted paths into ~/.claude/settings.json.
# E.g., the key "permissions.allowedBashCommands" maps to
#   settings.json → { "permissions": { "allowedBashCommands": [...] } }
"permissions.allowedBashCommands" = ["git status", "git diff", "git log", "ls", "pwd", "ruff check"]
"permissions.allowedReadPaths" = ["**/*.py", "**/*.toml", "**/*.md"]

[metadata]
license = "MIT"
homepage = "https://github.com/vipin/claude-lean-profiles"
```

**Validation rules:**
- `schema_version` must be ≤ tool's supported version
- `plugins.enabled` and `plugins.disabled` must not overlap
- `claude_md.mode` ∈ {replace, append, prepend}
- `settings_overlay` keys must be dotted-paths into the settings schema

---

## 9. Tech Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Language | Python ≥ 3.10 | Broad availability; matches user environment (Python 3.10/3.14 via brew); typing support |
| Tokenizer | `tiktoken` (`cl100k_base`) | Anthropic-family encoding; close approximation of Claude tokenizer |
| TUI library | `rich` | Best-in-class for tables/colors; widely installed |
| Config format | TOML | Human-editable, GitHub-friendly, no executable code |
| Other deps | stdlib only (besides `tiktoken` and `rich` above) | Minimize attack surface, install time, and breakage risk. Two declared deps total. |
| Package manager | `pyproject.toml` + `hatchling` | Modern PEP 621, no `setup.py` |
| Distribution | `pipx install claude-lean` | Isolated env, no global Python pollution |
| Testing | `pytest` + fixture `fake_claude_home` | Hermetic, no real `~/.claude/` modification |
| Lint / format | `ruff` (single tool for both) | Fast, low-config |
| Type check | `mypy --strict` on `src/` | Catch errors early |
| CI | GitHub Actions: test matrix (3.10, 3.11, 3.12, 3.14) × (macOS, Linux) | Match real user platforms |
| Docs | `mkdocs-material` on GitHub Pages | Standard, free hosting |
| License | MIT | Maximum reuse, compatible with marketplace contributions |

**Dependencies pinned:** `tiktoken >= 0.5.0`, `rich >= 13.0.0`. Everything else is stdlib.

---

## 10. Distribution & Packaging

- **Main repo:** `github.com/{user}/claude-lean` — the CLI
- **Profile repo:** `github.com/{user}/claude-lean-profiles` — community marketplace
- **PyPI:** `claude-lean` package, published from `main` on tag
- **Versioning:** semantic versioning, single source of truth in `__init__.py`
- **Releases:** GitHub Releases with changelog generated by `git-cliff`
- **Docs site:** `claude-lean.dev` (or GitHub Pages on the repo) built by `mkdocs`

Install for end users:

```bash
pipx install claude-lean         # primary
brew install claude-lean         # later, once stable
```

---

## 11. Testing Strategy

| Layer | What's tested | How |
|---|---|---|
| `tokenizer` | Count is deterministic and matches `tiktoken` directly | Unit tests with fixed strings |
| `scanner` | All expected files discovered in `fake_claude_home` fixture | Fixture-based test |
| `analyzer/rules/*` | Each rule fires (or doesn't) on its positive/negative fixtures | One test file per rule |
| `apply` (dry-run) | Generated diff matches expected, no files written | Snapshot test |
| `apply` (live) | Backup created, files written, restore works | Integration test on temp `~/.claude/` |
| `profile.manager` | install → use → restore is loss-free | Roundtrip test |
| `cli.py` | Subcommand routing works, `--help` exits cleanly | CLI test via subprocess |

**Fixtures:** A `tests/fixtures/fake_claude_home/` directory shaped exactly like a real `~/.claude/`, with miniature plugins, fake session logs, and a known-bad CLAUDE.md. Every test uses this; no test ever touches the real `~/.claude/`.

**Coverage target:** 85% line coverage on `src/`, enforced in CI.

---

## 12. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---:|---:|---|
| Tool corrupts user's `~/.claude/` | Low | High | Mandatory backup before any write; dry-run default; `restore` command |
| Plugin disable loses occasionally-used features | Medium | Low | Reversible via `profile restore`; recommendations show usage data |
| `tiktoken` token counts diverge from Anthropic's actual usage | High | Medium | Document the approximation; cross-check against observable session log sizes when `--with-usage` is enabled |
| Marketplace profile is malicious / breaks user setup | Low | Medium | All profile installs require explicit user confirmation and diff preview; no executable code in profiles (TOML-only); profiles are reviewed via PR before merging into marketplace |
| Claude Code internal format changes break the scanner | Medium | High | Scanner targets stable file conventions (`SKILL.md`, `settings.json`); version-detect and warn on unknown schemas |
| Tool becomes unnecessary as Anthropic ships native fixes | Medium | (positive) | Goal achieved; tool gracefully sunsets or pivots to advanced features Anthropic doesn't ship |
| Privacy concerns around scanning logs | Low | Medium | All scanning is local; no network calls except marketplace fetches (which are user-initiated, signed URLs); no telemetry |

---

## 13. Roadmap

> **Scope note for implementation:** This spec covers v1.0 architectural intent. **Each version below is its own separate implementation plan** — the immediate next step (after spec approval) is to invoke the `writing-plans` skill on **v0.1.0 only**. v0.2.0 onwards get their own plans later, informed by what we learn shipping v0.1.0.

| Version | Scope | Estimated effort | Acceptance criteria |
|---|---|---|---|
| **v0.1.0** | `audit` + `apply` (CLAUDE.md, settings.json, basic memory hygiene). 5 anti-pattern rules. CLI + JSON output. | 2–3 weeks part-time | Audit completes on a real install; apply with `--dry-run` produces a clean diff; restore works |
| **v0.2.0** | `profile` subcommand. 4 stock profiles. Snapshot/restore. | +1 week | `profile use python-ml` swaps config losslessly; `profile create` snapshots reliably |
| **v0.3.0** | `monitor` subcommand. Session log parser. Static reports. | +1 week | Surfaces real token counts from logs; `monitor report --since 7d` produces meaningful output |
| **v0.4.0** | Claude Code hooks. Auto-profile-by-cwd. Marketplace fetch (read-only). | +1–2 weeks | `.claude-lean` marker file triggers profile activation |
| **v1.0.0** | Marketplace publishing. Docs site. Research paper integrated. | +2 weeks | Marketplace PR workflow live; docs published; research paper sent to Anthropic |

Total estimated time-to-v1.0: **6–8 weeks part-time**.

---

## 14. Success Criteria

| # | Criterion | Verification |
|---|---|---|
| S1 | A default-everything install achieves ≥ 80% system prompt token reduction after `apply` with `aggressive` mode | Run `audit` before & after; compare totals |
| S2 | No data loss in `profile use` → `profile restore` roundtrip | Diff filesystem snapshots; CI test |
| S3 | Tool installs cleanly via `pipx install claude-lean` on macOS and Linux, Python 3.10+ | CI matrix |
| S4 | 100+ GitHub stars within 3 months of v1.0 | GitHub metrics |
| S5 | At least 1 cited feature request on Anthropic feedback channels referencing this tool's measurements | Public link |
| S6 | ≥ 5 community-contributed profiles in marketplace within 6 months of v1.0 | Marketplace repo |
| S7 | Zero reported issues of "the tool broke my Claude Code setup" | GitHub issues label `data-loss` |

---

## 15. Open Questions

| # | Question | Resolution path |
|---|---|---|
| Q1 | Should profile-switching mutate `settings.json` directly, or use a sidecar settings overlay? | Prototype both in v0.2; pick whichever is less invasive |
| Q2 | Are Claude Code hooks stable enough across CLI versions to rely on for v0.4? | Survey hook stability; gate v0.4 behind feature detection |
| Q3 | Should marketplace profiles be signed or trust-the-PR? | Start trust-the-PR; revisit if marketplace grows |
| Q4 | Expose programmatic API (`from claude_lean import audit`), or CLI-only? | Yes, expose; CLI is a thin wrapper around the library |
| Q5 | Windows support? | macOS + Linux first; Windows in v0.5 if demand exists |
| Q6 | How to handle users with `~/.claude/` symlinks (Dropbox, dotfiles)? | Resolve symlinks; warn if backup destination is on a sync'd drive |
| Q7 | What's the relationship to Anthropic's own future tooling? | Build for current state; design for graceful obsolescence |

---

## 16. Appendix A — Example Audit Output

```
$ claude-lean audit

claude-lean v0.1.0 — auditing /Users/vipin/.claude

Discovered:
  20 plugins enabled
  262 skills loaded
  49 agents loaded
  2 memory files in active project

Estimated system prompt overhead per turn: 58,234 tokens

Per-plugin breakdown (top 10 by cost):
  ┌─────────────────────────────┬─────────┬───────┬──────────┐
  │ Plugin                      │ Tokens  │ Usage │ Verdict  │
  ├─────────────────────────────┼─────────┼───────┼──────────┤
  │ engineering-advanced-skills │  9,840  │  31×  │  keep    │
  │ engineering-skills          │  9,210  │  47×  │  keep    │
  │ marketing-skills            │  4,512  │   0×  │  disable │
  │ c-level-skills              │  3,890  │   0×  │  disable │
  │ ra-qm-skills                │  3,210  │   0×  │  disable │
  │ superpowers                 │  2,840  │  18×  │  keep    │
  │ business-growth-skills      │  2,109  │   0×  │  disable │
  │ pm-skills                   │  1,980  │   0×  │  disable │
  │ content-creator             │  1,540  │   0×  │  disable │
  │ finance-skills              │    980  │   0×  │  disable │
  └─────────────────────────────┴─────────┴───────┴──────────┘

Findings (8):
  ⚠ unused-plugins (7)
      marketing-skills, c-level-skills, ra-qm-skills, business-growth-skills,
      pm-skills, content-creator, finance-skills
      → est. savings 18,221 tokens/turn

  ⚠ forcing-rules-in-claude-md (1)
      Line 1: "- Always use all agents"
      → causes sub-agent spawn for trivial tasks; est. cost 5-10×/task

  ⚠ stale-memory-snapshot (1)
      meditation_tts_project.md contains snapshot dated 2026-04-30
      (16 days old; should be in project README, not memory)

  ℹ memory-index-quality (1)
      All MEMORY.md descriptions look healthy (avg 78 chars)

Recommended changes:
  Estimated tokens saved per turn:  22,310
  Estimated multiplier gain:         2.4×

Run `claude-lean apply` to apply these changes interactively.
Run `claude-lean apply --auto` to apply all `safe`-tier recommendations.
```

---

## 17. Appendix B — Anti-Pattern Rule Catalog (initial)

| Rule ID | Triggers when | Severity | Estimated savings |
|---|---|---:|---|
| `unused-plugins` | Plugin has zero invocations in last 30 days AND not in user-declared stack | warn | 500–5000 tokens/turn per plugin |
| `forcing-rules-in-claude-md` | CLAUDE.md contains "always"/"must"/"every time" combined with "agent"/"tool" | warn | 5–10× per task |
| `stale-memory-snapshot` | Memory body has dated phrases like "as of YYYY-MM-DD" older than 30 days | warn | quality, not tokens |
| `vague-memory-description` | Description < 60 chars or contains `notes`, `stuff`, `info` | warn | quality (retrieval failure) |
| `duplicate-memories` | Two memory files have Jaccard similarity > 0.8 on tokens | warn | small, but compounds |
| `verbose-agent-examples` | Agent definition file > 200 total lines (frontmatter + body + examples combined) | info | 100–500 tokens/agent |
| `permissions-not-configured` | settings.json has no `permissions` block | info | round-trip cost |
| `memory-index-near-cap` | MEMORY.md > 180 lines | warn | risk of silent truncation |

---

## 18. References

- Claude Code documentation: https://docs.claude.com/en/docs/claude-code
- `tiktoken`: https://github.com/openai/tiktoken
- The sibling project: `/Users/vipin/Downloads/Opensource/claude-memory-architecture/` (foundational architecture docs that motivated this tool)

---

**End of Spec v1.**
