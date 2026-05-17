# FAQ

## General

### Why a separate CLI instead of a Claude Code plugin?

Because a plugin's metadata loads into Claude's context every turn — including the metadata of the plugin that's supposed to *save* you tokens. Putting `claude-lean` *outside* Claude Code means it costs zero tokens per conversation. The optimization is purely build-time.

### Is the "5×" claim real?

For a default-everything install on the most popular plugin packs, yes. The breakdown:

| Lever | Approx. saving |
|---|---|
| Disabling 7-10 truly unused plugin packs | ~45% |
| Rewriting forcing rules in CLAUDE.md | ~10% |
| Memory hygiene | ~5% |
| `settings.json` permission allowlist | ~8% |
| **Subtotal (audit + apply)** | **~2.0-2.5×** |
| Per-project profiles | ~35% |
| Hooks (auto-switch on cd, v0.4) | ~25% |
| **Subtotal (with profiles + hooks)** | **~5.0×** |

The first row of numbers (the 2.0-2.5× tier) is what v0.1 ships. The 5× target is end-of-roadmap, with profiles and hooks.

If you've already trimmed your setup manually, the savings will obviously be less — `claude-lean` measures, then suggests; it doesn't make magic numbers up.

### Does this work without `tiktoken` installed?

Yes. The fallback is a byte-based approximation (1 token ≈ 4 bytes). The *order* of plugins by cost is the same — only the absolute numbers differ. If you want exact counts, `pipx install 'claude-lean[accurate]'`.

### Will Anthropic eventually fix the underlying issues?

Probably some of them — and that would be great, the tool would gracefully sunset. The roadmap is built so that even if Anthropic ships lazy plugin loading tomorrow, the per-project profile feature still adds value.

## Setup

### What Python versions are supported?

3.11+. We need `tomllib` (3.11 stdlib) for profile parsing.

### Why `pipx` over `pip`?

`pipx` installs CLI tools into isolated environments, which is the right answer for end-user CLIs. `pip install --user` works too but can clash with other Python tools.

### Does it work on Windows?

Not tested. macOS and Linux only for v0.1. Windows support is on the roadmap; the path encoding logic just needs to handle backslashes.

### Where does `claude-lean` look for `~/.claude/`?

In order:
1. `--claude-home <path>` CLI flag
2. `$CLAUDE_HOME` environment variable
3. `~/.claude` (the default)

## Using It

### What if I disable a plugin and later need it?

`claude-lean restore --latest` reverts the most recent `apply`. Or just toggle the plugin back to `true` in `~/.claude/settings.json` — that's all `apply` actually changes.

### Can I add my own anti-pattern rules?

Not in v0.1 — rules are hard-coded. v0.2 will support a `~/.claude/claude-lean-rules.py` for user rules. You can fork the repo today and add a rule under `src/claude_lean/audit/rules/`; PRs welcome.

### Can I run this in CI?

Yes. `claude-lean audit --json-out audit.json` is non-interactive and produces a stable JSON output. You can fail builds on regression by parsing the result.

### What does "estimated savings" actually mean?

The tokens that would no longer load into Claude's system prompt if you applied the recommendation. It's a forward-looking estimate — measured against the static configuration, not against a specific conversation.

## Profiles

### Where do stock profiles live?

In the installed package: `src/claude_lean/profile/stock/*.toml`. They're bundled with the wheel.

### Can I make a custom profile?

Yes. Copy one of the stock profiles, edit it, save it locally, and pass the path to `profile use` (custom-path support is a v0.2 feature; for v0.1, drop your custom profile into the stock directory and reinstall — clunky but works).

### What about a marketplace?

v1.0. Community profiles will live in a separate repo (`claude-lean-profiles`) and be installable via `claude-lean profile install`. Roadmap.

### Will profiles conflict with `apply`?

A profile is just a more aggressive `apply` — it's all writes to `settings.json` and `CLAUDE.md`. They both go through the same backup system. Running `apply` after `profile use` is a no-op if the apply recommendations are already covered by the profile.

## Memory

### Why doesn't `claude-lean` auto-fix my memory files?

Memory rewriting is risky because memory content is policy + personal context. v0.1 only *reports*. v0.2 will add `apply --rewrite-memories` behind an explicit opt-in flag.

### What's the 200-line cap?

Claude Code's harness truncates `MEMORY.md` after 200 lines. Memories referenced beyond that line are silently invisible. The `memory-index-near-cap` rule warns when you're approaching it.

### Why are my memory descriptions flagged as "vague"?

Because Claude uses the description as the only signal for whether to *load* the memory body. A description like "notes" doesn't match any topic, so the memory body never gets loaded. Aim for 60+ characters mentioning the topic, constraint, or fact.

## Troubleshooting

### "Claude Code home not found at /Users/you/.claude"

Either your install is at a non-default location (use `--claude-home`), or you haven't run `claude` yet to initialize it.

### Audit reports "Agents: 0" but I know I have agents

Agents must live under an `agents/` directory inside a plugin. If your agents are at `~/.claude/agents/`, that's the global-agent location and v0.1 doesn't scan it yet (v0.2 will).

### "Estimated savings" looks way too high

Without `tiktoken`, the byte-based estimate over-counts on text-heavy content. The relative order is still correct; install the `accurate` extra for exact numbers.

### Rich output is garbled in my terminal

`rich` auto-detects terminal capabilities. If output looks weird, try `--json` (machine-readable) or set `TERM=dumb` for plain text.

### Tests fail after `pip install`

Make sure you installed with the `dev` extra:

```bash
pip install -e '.[dev]'
pytest
```

## Privacy

### Does `claude-lean` send any data anywhere?

No. Every operation is local. The optional `profile install` from a marketplace (v1.0) is opt-in and shows you what URL it fetches from.

### What's logged?

Nothing by default. The `monitor` subcommand (v0.3) will *read* `~/.claude/projects/*/` session logs (which Claude Code already writes), but nothing is sent outside your machine.
