"""Rule: detect memory files that contain stale snapshot state.

Memories are policy + intent; ephemeral state (setup commands, version pins,
'as of YYYY-MM-DD' snapshots) should live in project READMEs or code,
not in memory where it silently goes wrong.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from claude_lean.audit.rules._base import Rule, Finding, Severity


_DATE_AS_OF = re.compile(r"as\s+of\s+(\d{4})[-/](\d{1,2})[-/](\d{1,2})", re.IGNORECASE)
_STALE_THRESHOLD_DAYS = 30


class StaleMemoryRule:
    rule_id = "stale-memory-snapshot"
    severity = Severity.WARN
    title = "Memory file contains a dated snapshot that may be stale"

    def evaluate(self, inventory) -> list[Finding]:
        findings: list[Finding] = []
        now = datetime.now(timezone.utc).date()

        for project_key, memories in inventory.memory_files.items():
            for mem in memories:
                match = _DATE_AS_OF.search(mem.body_excerpt)
                if not match:
                    continue
                try:
                    year, month, day = (int(x) for x in match.groups())
                    snap_date = datetime(year, month, day, tzinfo=timezone.utc).date()
                except (ValueError, TypeError):
                    continue
                age_days = (now - snap_date).days
                if age_days < _STALE_THRESHOLD_DAYS:
                    continue
                findings.append(
                    Finding(
                        rule_id=self.rule_id,
                        severity=self.severity,
                        title=f"{mem.path.name}: snapshot dated {snap_date} (>{age_days}d old)",
                        evidence=(
                            f"Memory file contains 'as of {snap_date.isoformat()}' "
                            f"({age_days} days old). Snapshot-style state in memory "
                            f"silently goes wrong as the project evolves."
                        ),
                        suggested_action=(
                            "Move the snapshot section to the project's README. "
                            "Keep only policy/intent/why in the memory file."
                        ),
                        estimated_savings_tokens=0,  # quality
                        target=str(mem.path),
                        metadata={
                            "project": project_key,
                            "snapshot_date": snap_date.isoformat(),
                            "age_days": age_days,
                        },
                    )
                )
        return findings
