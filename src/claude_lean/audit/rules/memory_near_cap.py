"""Rule: detect MEMORY.md files approaching the 200-line truncation cap.

Lines after 200 in MEMORY.md are silently truncated by the harness, making
the memories they point to invisible to retrieval.
"""

from __future__ import annotations

from claude_lean.audit.rules._base import Rule, Finding, Severity


_CAP = 200
_WARN_AT = 180


class MemoryNearCapRule:
    rule_id = "memory-index-near-cap"
    severity = Severity.WARN
    title = "MEMORY.md approaching the 200-line truncation cap"

    def evaluate(self, inventory) -> list[Finding]:
        findings: list[Finding] = []
        for project_key, index_info in inventory.memory_indexes.items():
            try:
                lines = index_info.path.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            line_count = len(lines)
            if line_count < _WARN_AT:
                continue
            severity = Severity.CRITICAL if line_count > _CAP else Severity.WARN
            over_or_near = (
                f"{line_count - _CAP} lines past the cap (invisible)"
                if line_count > _CAP
                else f"{_CAP - line_count} lines below cap"
            )
            findings.append(
                Finding(
                    rule_id=self.rule_id,
                    severity=severity,
                    title=f"{index_info.path.name}: {line_count} lines ({over_or_near})",
                    evidence=(
                        f"MEMORY.md has {line_count} lines. The Claude Code "
                        f"harness truncates this file after {_CAP} lines, "
                        f"making memories referenced beyond that point "
                        f"invisible to retrieval."
                    ),
                    suggested_action=(
                        "Consolidate related memories, delete obsolete entries, "
                        "or sharpen vague descriptions to make each line earn its place."
                    ),
                    target=str(index_info.path),
                    metadata={"project": project_key, "line_count": line_count},
                )
            )
        return findings
