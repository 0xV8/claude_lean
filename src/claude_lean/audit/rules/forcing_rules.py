"""Rule: detect 'forcing rules' in CLAUDE.md that cause expensive sub-agent spawns.

A forcing rule is one that says 'always' / 'must' / 'every time' combined with
'agent' or 'tool'. These rules cause Claude to delegate to sub-agents even for
trivial work, costing 5-10x the tokens of direct execution.
"""

from __future__ import annotations

import re

from claude_lean.audit.rules._base import Rule, Finding, Severity


_FORCING_PATTERN = re.compile(
    r"\b(always|must|every\s+time|need\s+to|have\s+to)\b.*\b(agents?|sub[- ]?agents?|tools?|skills?)\b",
    re.IGNORECASE,
)


class ForcingRulesRule:
    rule_id = "forcing-rules-in-claude-md"
    severity = Severity.WARN
    title = "Forcing rules in CLAUDE.md cause expensive sub-agent spawns"

    def evaluate(self, inventory) -> list[Finding]:
        findings: list[Finding] = []
        path = inventory.claude_md_path
        if path is None or not path.is_file():
            return findings

        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return findings

        for lineno, line in enumerate(text.splitlines(), start=1):
            if _FORCING_PATTERN.search(line):
                findings.append(
                    Finding(
                        rule_id=self.rule_id,
                        severity=self.severity,
                        title=f"Forcing rule on line {lineno} of CLAUDE.md",
                        evidence=f"Line {lineno}: {line.strip()!r}",
                        suggested_action=(
                            "Rewrite this rule to be conditional. E.g., "
                            "'Always use agents' → 'Use agents when work is "
                            "specialized or parallelizable, not for simple edits'."
                        ),
                        estimated_savings_tokens=0,  # quality, not size
                        target=str(path),
                        metadata={"line": lineno, "content": line.strip()},
                    )
                )
        return findings
