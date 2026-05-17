"""Interactive wizard that asks the user about their stack and returns a plan."""

from __future__ import annotations

from dataclasses import dataclass, field

from rich.console import Console
from rich.prompt import Prompt, Confirm


_ENGINEERING_STACKS = ["python", "javascript/typescript", "rust", "go", "ml/ai", "devops", "frontend", "mobile", "other"]
_NON_ENG_WORK = ["marketing", "sales", "finance", "product", "regulatory", "none"]


@dataclass
class WizardResult:
    """User's choices, ready to feed into the generator."""

    primary_stacks: list[str] = field(default_factory=list)
    non_eng_work: list[str] = field(default_factory=list)
    aggressiveness: str = "balanced"  # conservative | balanced | aggressive
    confirm_apply: bool = False


def run_wizard(*, console: Console | None = None) -> WizardResult:
    """Run the interactive wizard. Returns the user's choices."""
    console = console or Console()
    console.print()
    console.rule("[bold]claude-lean apply[/bold]")
    console.print()
    console.print("A few questions to tailor recommendations to your work.")
    console.print()

    primary = _multi_select(console, "What's your primary stack?", _ENGINEERING_STACKS)
    non_eng = _multi_select(
        console,
        "Any non-engineering work types? ('none' is fine)",
        _NON_ENG_WORK,
        default_index=len(_NON_ENG_WORK) - 1,
    )
    aggressiveness = _single_select(
        console,
        "How aggressive should optimizations be?",
        ["conservative", "balanced", "aggressive"],
        default="balanced",
    )
    confirm = Confirm.ask(
        "Apply changes now? (Will show diff first; nothing is destructive)",
        default=False,
        console=console,
    )

    return WizardResult(
        primary_stacks=primary,
        non_eng_work=non_eng,
        aggressiveness=aggressiveness,
        confirm_apply=confirm,
    )


def _multi_select(
    console: Console,
    prompt: str,
    choices: list[str],
    *,
    default_index: int | None = None,
) -> list[str]:
    """Naive stdlib-friendly multi-select: comma-separated indices."""
    console.print(f"[bold]{prompt}[/bold]")
    for i, c in enumerate(choices, start=1):
        marker = " (default)" if default_index == i - 1 else ""
        console.print(f"  [cyan]{i}[/cyan]. {c}{marker}")
    default_str = str(default_index + 1) if default_index is not None else ""
    raw = Prompt.ask(
        "Enter numbers separated by commas",
        default=default_str,
        console=console,
        show_default=bool(default_str),
    )
    selected: list[str] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            idx = int(chunk)
            if 1 <= idx <= len(choices):
                selected.append(choices[idx - 1])
        except ValueError:
            pass
    console.print()
    return selected


def _single_select(
    console: Console,
    prompt: str,
    choices: list[str],
    *,
    default: str,
) -> str:
    return Prompt.ask(
        prompt,
        choices=choices,
        default=default,
        console=console,
    )
