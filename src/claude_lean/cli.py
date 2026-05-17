"""claude-lean command-line interface."""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path

from rich.console import Console
from rich.syntax import Syntax

from claude_lean import __version__
from claude_lean.apply.generator import GeneratorPlan, build_plan, write_plan
from claude_lean.apply.wizard import WizardResult, run_wizard
from claude_lean.audit.analyzer import analyze
from claude_lean.audit.report import render_json, render_terminal
from claude_lean.audit.scanner import scan
from claude_lean.common.backup import (
    latest_snapshot,
    list_snapshots,
    load_manifest,
    make_snapshot,
    restore_snapshot,
)
from claude_lean.common.claude_paths import ClaudePaths
from claude_lean.profile.manager import ProfileManager


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    paths = ClaudePaths.discover(Path(args.claude_home) if args.claude_home else None)

    if args.command is None:
        parser.print_help()
        return 0

    if not paths.exists() and args.command != "version":
        Console(stderr=True).print(
            f"[red]Error:[/red] Claude Code home not found at [cyan]{paths.home}[/cyan]\n"
            f"Set CLAUDE_HOME or pass --claude-home to override."
        )
        return 2

    handler = _COMMANDS[args.command]
    return handler(args, paths)


# ---- argparse ----


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="claude-lean",
        description="Get 5x more from your Claude Code token budget.",
    )
    parser.add_argument("--version", action="version", version=f"claude-lean {__version__}")
    parser.add_argument(
        "--claude-home",
        default=None,
        help="Override location of Claude Code home (default: ~/.claude)",
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    # audit
    p_audit = sub.add_parser("audit", help="Scan ~/.claude/ and report opportunities")
    p_audit.add_argument("--json", action="store_true", help="Emit JSON instead of terminal output")
    p_audit.add_argument(
        "--json-out", type=Path, default=None, help="Write JSON to a file (implies --json)"
    )

    # apply
    p_apply = sub.add_parser("apply", help="Apply recommendations (interactive)")
    p_apply.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing anything",
    )
    p_apply.add_argument(
        "--yes",
        action="store_true",
        help="Skip interactive confirmation (still respects --dry-run)",
    )

    # restore
    p_restore = sub.add_parser("restore", help="Restore a previous snapshot")
    p_restore.add_argument(
        "--latest", action="store_true", help="Restore the most recent snapshot"
    )
    p_restore.add_argument(
        "--list", action="store_true", help="List available snapshots and exit"
    )
    p_restore.add_argument(
        "--snapshot",
        default=None,
        help="Restore a specific snapshot by name (timestamp folder)",
    )

    # profile
    p_profile = sub.add_parser("profile", help="Manage per-project context profiles")
    profile_sub = p_profile.add_subparsers(dest="profile_command", metavar="<subcommand>")

    profile_sub.add_parser("list", help="List installed profiles")

    p_show = profile_sub.add_parser("show", help="Show a profile's contents")
    p_show.add_argument("name")

    p_use = profile_sub.add_parser("use", help="Apply a profile to ~/.claude/")
    p_use.add_argument("name")
    p_use.add_argument("--dry-run", action="store_true")
    p_use.add_argument("--yes", action="store_true")

    return parser


# ---- command handlers ----


def cmd_audit(args, paths: ClaudePaths) -> int:
    inventory = scan(paths)
    result = analyze(inventory)
    if args.json or args.json_out:
        text = render_json(result)
        if args.json_out:
            args.json_out.parent.mkdir(parents=True, exist_ok=True)
            args.json_out.write_text(text, encoding="utf-8")
        else:
            print(text)
    else:
        render_terminal(result)
    return 0 if result.critical_count == 0 else 1


def cmd_apply(args, paths: ClaudePaths) -> int:
    console = Console()
    if args.yes:
        wizard = WizardResult(
            primary_stacks=["python"],
            non_eng_work=["none"],
            aggressiveness="balanced",
            confirm_apply=not args.dry_run,
        )
    else:
        wizard = run_wizard(console=console)

    plan = build_plan(paths, wizard)
    if not plan.has_changes:
        console.print("[green]✓[/green] No changes proposed. Your setup already looks lean.")
        return 0

    _show_plan_diff(console, plan)

    if args.dry_run:
        console.print("[dim](--dry-run; nothing written)[/dim]")
        return 0

    if not (args.yes or wizard.confirm_apply):
        console.print("Aborted. Re-run with --yes or answer 'y' to apply.")
        return 0

    files_to_backup = [plan.settings_path, plan.claude_md_path]
    snap_root = make_snapshot(paths, files_to_backup, reason="apply")
    console.print(f"  Backup: [dim]{snap_root}[/dim]")
    write_plan(plan)
    console.print("[green]✓[/green] Changes applied. Restore with: [cyan]claude-lean restore --latest[/cyan]")
    return 0


def cmd_restore(args, paths: ClaudePaths) -> int:
    console = Console()
    snaps = list_snapshots(paths)
    if args.list:
        if not snaps:
            console.print("No snapshots found.")
            return 0
        console.print("[bold]Available snapshots (newest first):[/bold]")
        for snap in snaps:
            manifest = load_manifest(snap)
            reason = manifest.reason if manifest else "?"
            files = len(manifest.files) if manifest else 0
            console.print(f"  {snap.name}  ([dim]{reason}, {files} files[/dim])")
        return 0

    if args.snapshot:
        target = paths.backups_dir / args.snapshot
    elif args.latest:
        target = latest_snapshot(paths)
    else:
        console.print("Specify --latest, --list, or --snapshot <name>.")
        return 2

    if target is None or not target.is_dir():
        console.print(f"[red]No such snapshot:[/red] {target}")
        return 2

    restored = restore_snapshot(paths, target)
    console.print(f"[green]✓[/green] Restored {len(restored)} file(s) from {target.name}")
    return 0


def cmd_profile(args, paths: ClaudePaths) -> int:
    console = Console()
    mgr = ProfileManager(paths=paths)
    sub = args.profile_command

    if sub is None or sub == "list":
        profiles = mgr.list_stock()
        if not profiles:
            console.print("No stock profiles found.")
            return 0
        console.print("[bold]Stock profiles:[/bold]")
        for p in profiles:
            console.print(f"  [cyan]{p.name}[/cyan] — {p.description}")
        return 0

    if sub == "show":
        prof = mgr.get(args.name)
        if prof is None:
            console.print(f"[red]No such profile:[/red] {args.name}")
            return 2
        if prof.source_path:
            console.print(Syntax(prof.source_path.read_text(encoding="utf-8"), "toml"))
        return 0

    if sub == "use":
        prof = mgr.get(args.name)
        if prof is None:
            console.print(f"[red]No such profile:[/red] {args.name}")
            return 2
        changes = mgr.apply(prof)
        old_settings = changes["old_settings"]
        new_settings = changes["new_settings"]
        old_md = changes["old_claude_md"]
        new_md = changes["new_claude_md"]

        # Show summary
        console.print(f"Profile: [bold cyan]{prof.name}[/bold cyan] — {prof.description}")
        console.print()
        _show_dict_diff(console, "settings.json", old_settings, new_settings)
        _show_text_diff(console, "CLAUDE.md", old_md, new_md)

        if args.dry_run:
            console.print("[dim](--dry-run; nothing written)[/dim]")
            return 0
        if not args.yes:
            from rich.prompt import Confirm
            ok = Confirm.ask("Apply this profile?", default=False, console=console)
            if not ok:
                console.print("Aborted.")
                return 0

        snap = make_snapshot(
            paths,
            [paths.settings_json, paths.global_claude_md],
            reason=f"profile use {prof.name}",
        )
        console.print(f"  Backup: [dim]{snap}[/dim]")
        paths.settings_json.parent.mkdir(parents=True, exist_ok=True)
        paths.settings_json.write_text(
            json.dumps(new_settings, indent=2) + "\n", encoding="utf-8"
        )
        paths.global_claude_md.parent.mkdir(parents=True, exist_ok=True)
        paths.global_claude_md.write_text(new_md, encoding="utf-8")
        console.print(f"[green]✓[/green] Active profile: {prof.name}")
        return 0

    console.print(f"Unknown profile subcommand: {sub}")
    return 2


def cmd_version(args, paths: ClaudePaths) -> int:  # noqa: ARG001
    print(f"claude-lean {__version__}")
    return 0


# ---- helpers ----


def _show_plan_diff(console: Console, plan: GeneratorPlan) -> None:
    console.print()
    console.rule("[bold]Proposed changes[/bold]")
    console.print()
    if plan.plugin_disables:
        console.print(f"[bold]Plugins to disable[/bold] ({len(plan.plugin_disables)}):")
        for p in plan.plugin_disables:
            console.print(f"  [red]- {p}[/red]")
        console.print()
    _show_text_diff(console, "CLAUDE.md", plan.old_claude_md, plan.new_claude_md)


def _show_dict_diff(console: Console, label: str, old: dict, new: dict) -> None:
    old_text = json.dumps(old, indent=2, sort_keys=True)
    new_text = json.dumps(new, indent=2, sort_keys=True)
    _show_text_diff(console, label, old_text, new_text)


def _show_text_diff(console: Console, label: str, old: str, new: str) -> None:
    if old == new:
        return
    console.print(f"[bold]Diff for {label}:[/bold]")
    diff = difflib.unified_diff(
        old.splitlines(),
        new.splitlines(),
        fromfile=f"{label} (current)",
        tofile=f"{label} (proposed)",
        n=2,
        lineterm="",
    )
    for line in diff:
        if line.startswith("+") and not line.startswith("+++"):
            console.print(f"  [green]{line}[/green]")
        elif line.startswith("-") and not line.startswith("---"):
            console.print(f"  [red]{line}[/red]")
        elif line.startswith("@@"):
            console.print(f"  [cyan]{line}[/cyan]")
        else:
            console.print(f"  {line}")
    console.print()


_COMMANDS = {
    "audit": cmd_audit,
    "apply": cmd_apply,
    "restore": cmd_restore,
    "profile": cmd_profile,
}


if __name__ == "__main__":
    sys.exit(main())
