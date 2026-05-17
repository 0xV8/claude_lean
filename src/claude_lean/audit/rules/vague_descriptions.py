"""Rule: detect memory index entries with descriptions too vague to retrieve on.

A vague description in MEMORY.md silently breaks retrieval: Claude won't
pull the memory body in because the description doesn't signal relevance.
"""

from __future__ import annotations

from claude_lean.audit.rules._base import Rule, Finding, Severity


_MIN_DESC_CHARS = 60
_GENERIC_WORDS = frozenset({"notes", "stuff", "info", "details", "things"})


class VagueDescriptionsRule:
    rule_id = "vague-memory-description"
    severity = Severity.WARN
    title = "Memory descriptions too vague for reliable retrieval"

    def evaluate(self, inventory) -> list[Finding]:
        findings: list[Finding] = []
        for project_key, memories in inventory.memory_files.items():
            for mem in memories:
                desc = (mem.description or "").strip()
                if not desc:
                    findings.append(
                        Finding(
                            rule_id=self.rule_id,
                            severity=self.severity,
                            title=f"{mem.path.name}: no description in frontmatter",
                            evidence="The `description:` field is missing or empty.",
                            suggested_action=(
                                "Add a specific one-line description to the "
                                "frontmatter. The description is the only signal "
                                "Claude has for whether to load this memory."
                            ),
                            target=str(mem.path),
                            metadata={"project": project_key},
                        )
                    )
                    continue
                lowered = desc.lower()
                generic_hit = any(w in lowered.split() for w in _GENERIC_WORDS)
                too_short = len(desc) < _MIN_DESC_CHARS
                if generic_hit or too_short:
                    reason = []
                    if too_short:
                        reason.append(f"only {len(desc)} chars (target ≥{_MIN_DESC_CHARS})")
                    if generic_hit:
                        reason.append("contains generic words ('notes', 'stuff', etc.)")
                    findings.append(
                        Finding(
                            rule_id=self.rule_id,
                            severity=self.severity,
                            title=f"{mem.path.name}: vague description",
                            evidence=f"Description {desc!r} — {', '.join(reason)}.",
                            suggested_action=(
                                "Rewrite to be specific: mention the topic, "
                                "the constraint, or the fact. This is what "
                                "determines whether the memory ever gets loaded."
                            ),
                            target=str(mem.path),
                            metadata={"project": project_key, "description": desc},
                        )
                    )
        return findings
