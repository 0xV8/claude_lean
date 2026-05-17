# Safety Model

`claude-lean` mutates files in your `~/.claude/` directory. This document explains exactly when and how, and what the safety guarantees are.

## The Three Promises

> **1. Nothing is destroyed without a backup first.**
> **2. You can always go back, with one command.**
> **3. You see a diff before any write.**

## What Gets Modified

| File | Modified by | When |
|---|---|---|
| `~/.claude/CLAUDE.md` | `apply`, `profile use` | When recommendations or a profile changes the content |
| `~/.claude/settings.json` | `apply`, `profile use` | When plugin enables/disables change |
| `~/.claude/.claude-lean-backups/` | All write commands | A snapshot is added before any other write |

## What Is Never Modified

| File | Why |
|---|---|
| `~/.claude/settings.local.json` | Reserved for your local-only overrides |
| `~/.claude/plugins/cache/**` | Plugin contents are upstream — we never touch them |
| `~/.claude/projects/*/memory/*.md` | Memory hygiene rules *report* problems; you fix them by hand (auto-rewriting memories is a v0.2 feature behind an explicit `--rewrite-memories` flag) |
| `~/.claude/history.jsonl` | Conversation history — read-only for `monitor` (v0.3) |
| Anything outside `~/.claude/` | Out of scope |

## Backup Mechanics

Every write operation does this, in order:

1. **Snapshot.** Files about to be modified are copied to `~/.claude/.claude-lean-backups/{ISO-timestamp}/` with the same relative structure
2. **Manifest written.** A `manifest.json` records what's in the snapshot, when it was made, and why
3. **Mutation.** The new content is written to the original files
4. **Confirmation printed.** The snapshot path is shown in the terminal output

Example snapshot directory:

```
~/.claude/.claude-lean-backups/2026-05-17T08-42-11-123456Z/
├── manifest.json
├── CLAUDE.md
└── settings.json
```

Example manifest:

```json
{
  "timestamp": "2026-05-17T08-42-11-123456Z",
  "reason": "apply",
  "files": ["CLAUDE.md", "settings.json"]
}
```

## Restore

Restoring is the inverse: files in a snapshot are copied back over the live ones.

```bash
# List all snapshots
claude-lean restore --list

# Restore the most recent
claude-lean restore --latest

# Restore a specific one
claude-lean restore --snapshot 2026-05-17T08-42-11-123456Z
```

**Restore is also non-destructive.** It restores files that were *in* the snapshot. Files that exist now but weren't backed up are left untouched.

## Dry-Run Semantics

| Flag | Behavior |
|---|---|
| `--dry-run` | Show what would change; write nothing; exit cleanly |
| (no flag, TTY stdout) | Interactive: show diff, ask for confirmation |
| (no flag, non-TTY stdout) | Treated as `--dry-run` to prevent accidental pipes mutating state |
| `--yes` | Skip the interactive confirmation; still respects `--dry-run` if set |
| `--yes --dry-run` | Same as `--dry-run` (the safer flag wins) |

## What "Aggressive" Means

`apply` has three modes: `conservative`, `balanced` (default), `aggressive`.

| Mode | Plugin disable policy |
|---|---|
| `conservative` | Only disable plugins that are clearly unused (matching the LIKELY_UNUSED_FOR_ENGINEERING list) and the user explicitly *didn't* mention the corresponding work type |
| `balanced` (default) | Same as conservative, plus disable plugins clearly outside the declared stack |
| `aggressive` | Disable everything not in the core engineering set + explicit user opt-ins; recommended only if you trust yourself to `restore --latest` if you regret it |

## Concurrent Sessions

`claude-lean` does **not** lock `~/.claude/`. If two `claude-lean` processes write simultaneously (or one writes while Claude Code is loading), the second writer wins.

In practice this is fine because:
- Snapshots are timestamped, so they don't collide
- Each `apply` / `profile use` is a single fast write
- Concurrent multi-process modification of `~/.claude/` is not a normal usage pattern

If you regularly multi-process modify it, file an issue and we'll add a lockfile.

## What Could Still Go Wrong

| Risk | Mitigation |
|---|---|
| You `apply --aggressive` and regret it | `claude-lean restore --latest` |
| You disable a plugin you actually use | `claude-lean profile use {profile}` to switch back, or `restore` |
| Snapshot dir grows over time | `~/.claude/.claude-lean-backups/` is plain folders; delete what you don't need. (v0.2 will add `claude-lean backup prune --older-than 30d`.) |
| Disk fills up during snapshot | Snapshot fails (atomic per-file copy); the original files are untouched |
| `~/.claude/` is a symlink to a network drive | Snapshots write to the same drive; restore works the same way. We don't follow or break symlinks |
| You break the tool itself | The tool only reads its own code from your `pipx`/`pip` environment; nothing in your install is touched |

## Reporting Safety Issues

If you find a way `claude-lean` can corrupt or destroy data without warning, please open an issue tagged `data-loss` immediately. Safety bugs jump the queue.
