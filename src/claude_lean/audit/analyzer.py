"""Run all registered rules over an inventory and produce a finding list."""

from __future__ import annotations

from dataclasses import dataclass, field

from claude_lean.audit.rules import all_rules
from claude_lean.audit.rules._base import Finding, Severity
from claude_lean.audit.scanner import Inventory


@dataclass
class AuditResult:
    """The full audit output."""

    inventory: Inventory
    findings: list[Finding] = field(default_factory=list)

    @property
    def total_estimated_savings(self) -> int:
        return sum(f.estimated_savings_tokens for f in self.findings)

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.CRITICAL)

    @property
    def warn_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.WARN)

    @property
    def info_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.INFO)

    @property
    def multiplier_gain(self) -> float:
        """Estimated tokens-per-conversation multiplier after applying recommendations."""
        baseline = self.inventory.estimated_system_prompt_tokens
        if baseline <= 0:
            return 1.0
        saved = self.total_estimated_savings
        remaining = max(baseline - saved, 1)
        return round(baseline / remaining, 2)


def analyze(inventory: Inventory) -> AuditResult:
    """Run every registered rule and collect findings."""
    findings: list[Finding] = []
    for rule in all_rules():
        findings.extend(rule.evaluate(inventory))
    return AuditResult(inventory=inventory, findings=findings)
