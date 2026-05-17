"""Base types for audit rules. A rule looks at the inventory and emits findings."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from claude_lean.audit.scanner import Inventory


class Severity(str, Enum):
    INFO = "info"
    WARN = "warn"
    CRITICAL = "critical"


@dataclass
class Finding:
    """A single anti-pattern instance discovered by a rule."""

    rule_id: str
    severity: Severity
    title: str
    evidence: str
    suggested_action: str
    estimated_savings_tokens: int = 0
    target: str | None = None  # plugin name / file path / etc.
    metadata: dict = field(default_factory=dict)


class Rule(Protocol):
    """Audit rule contract."""

    rule_id: str
    severity: Severity
    title: str

    def evaluate(self, inventory: "Inventory") -> list[Finding]:
        ...
