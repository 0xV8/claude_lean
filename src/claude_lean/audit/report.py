"""Render audit results to terminal (rich) or JSON."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from rich.console import Console
from rich.table import Table
from rich import box

from claude_lean.audit.analyzer import AuditResult
from claude_lean.audit.rules._base import Severity
from claude_lean.common.tokenizer import accuracy_label


_SEVERITY_GLYPH = {
    Severity.INFO: "[cyan]ℹ[/cyan]",
    Severity.WARN: "[yellow]⚠[/yellow]",
    Severity.CRITICAL: "[red]✖[/red]",
}


def render_terminal(result: AuditResult, console: Console | None = None) -> None:
    """Render the audit to the terminal using rich."""
    console = console or Console()
    inv = result.inventory

    # Header
    console.print()
    console.rule(f"[bold]claude-lean audit[/bold] · {inv.claude_home}")
    console.print(f"[dim]Token measurement: {accuracy_label()}[/dim]")
    console.print()

    # Headline stats
    console.print(
        f"  Plugins enabled: [bold]{sum(1 for p in inv.plugins if p.enabled)}[/bold]  "
        f"·  Skills: [bold]{sum(len(p.skills) for p in inv.plugins if p.enabled)}[/bold]  "
        f"·  Agents: [bold]{sum(len(p.agents) for p in inv.plugins if p.enabled)}[/bold]"
    )
    console.print(
        f"  Estimated system-prompt overhead per turn: "
        f"[bold yellow]{inv.estimated_system_prompt_tokens:,}[/bold yellow] tokens"
    )
    console.print()

    # Per-plugin table (top 10 by cost)
    enabled_plugins = sorted(
        (p for p in inv.plugins if p.enabled),
        key=lambda p: p.tokens_total,
        reverse=True,
    )
    top = enabled_plugins[:10]
    if top:
        table = Table(
            title="Top 10 enabled plugins by token cost",
            box=box.SIMPLE_HEAVY,
            show_lines=False,
        )
        table.add_column("Plugin", style="cyan")
        table.add_column("Skills", justify="right")
        table.add_column("Agents", justify="right")
        table.add_column("Total tokens", justify="right", style="bold")
        for p in top:
            table.add_row(
                p.name,
                f"{p.tokens_skills:,}",
                f"{p.tokens_agents:,}",
                f"{p.tokens_total:,}",
            )
        console.print(table)
        console.print()

    # Findings
    if result.findings:
        console.print(
            f"[bold]Findings:[/bold] "
            f"[red]{result.critical_count} critical[/red] · "
            f"[yellow]{result.warn_count} warn[/yellow] · "
            f"[cyan]{result.info_count} info[/cyan]"
        )
        console.print()
        # Group findings by rule_id
        by_rule: dict[str, list] = {}
        for f in result.findings:
            by_rule.setdefault(f.rule_id, []).append(f)
        for rule_id, group in by_rule.items():
            first = group[0]
            glyph = _SEVERITY_GLYPH.get(first.severity, "·")
            console.print(f"{glyph} [bold]{rule_id}[/bold] ({len(group)})")
            for f in group:
                console.print(f"    {f.title}")
                if f.estimated_savings_tokens:
                    console.print(
                        f"    [dim]→ est. savings: {f.estimated_savings_tokens:,} tokens/turn[/dim]"
                    )
            console.print()
    else:
        console.print("[green]✓[/green] No anti-patterns detected. Your setup looks clean.")
        console.print()

    # Bottom line
    savings = result.total_estimated_savings
    if savings > 0:
        console.print(
            f"  [bold]Estimated tokens saved per turn if applied:[/bold] "
            f"[green]{savings:,}[/green] tokens  "
            f"(≈ [bold green]{result.multiplier_gain}×[/bold green] more headroom)"
        )
        console.print()
        console.print(
            "  Next: run [bold cyan]claude-lean apply[/bold cyan] to act on these recommendations."
        )
    console.print()


def render_json(result: AuditResult) -> str:
    """Render the audit as a stable JSON document."""
    inv = result.inventory
    doc = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "claude_home": str(inv.claude_home),
        "tokenizer_accuracy": accuracy_label(),
        "totals": {
            "plugins_enabled": sum(1 for p in inv.plugins if p.enabled),
            "plugins_installed": len(inv.plugins),
            "skills_loaded": sum(len(p.skills) for p in inv.plugins if p.enabled),
            "agents_loaded": sum(len(p.agents) for p in inv.plugins if p.enabled),
            "estimated_system_prompt_tokens": inv.estimated_system_prompt_tokens,
            "claude_md_tokens": inv.claude_md_tokens,
        },
        "by_plugin": [
            {
                "name": p.name,
                "marketplace": p.marketplace,
                "enabled": p.enabled,
                "tokens_skills": p.tokens_skills,
                "tokens_agents": p.tokens_agents,
                "tokens_mcp": p.tokens_mcp,
                "tokens_total": p.tokens_total,
            }
            for p in sorted(inv.plugins, key=lambda x: x.tokens_total, reverse=True)
        ],
        "findings": [
            {
                "rule_id": f.rule_id,
                "severity": f.severity.value,
                "title": f.title,
                "evidence": f.evidence,
                "suggested_action": f.suggested_action,
                "estimated_savings_tokens": f.estimated_savings_tokens,
                "target": f.target,
                "metadata": f.metadata,
            }
            for f in result.findings
        ],
        "recommendations_summary": {
            "estimated_tokens_saved_per_turn": result.total_estimated_savings,
            "estimated_multiplier_gain": result.multiplier_gain,
        },
    }
    return json.dumps(doc, indent=2, default=str)
