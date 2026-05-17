"""Rule: detect enabled plugins that look unused.

v0.1 heuristic: a plugin counts as "unused" if its name matches a list of
plugin packs that are typically irrelevant for engineering workflows AND
it's currently enabled. A later version will cross-reference session log
invocations for a measured judgment.
"""

from __future__ import annotations

from claude_lean.audit.rules._base import Rule, Finding, Severity

# Plugin packs that an engineering-focused user almost never invokes.
LIKELY_UNUSED_FOR_ENGINEERING = {
    "marketing-skills",
    "c-level-skills",
    "ra-qm-skills",
    "business-growth-skills",
    "finance-skills",
    "pm-skills",
    "content-creator",
    "product-skills",
}


class UnusedPluginsRule:
    rule_id = "unused-plugins"
    severity = Severity.WARN
    title = "Enabled plugins that may go unused"

    def evaluate(self, inventory) -> list[Finding]:
        findings: list[Finding] = []
        for plugin in inventory.plugins:
            if not plugin.enabled:
                continue
            if plugin.name not in LIKELY_UNUSED_FOR_ENGINEERING:
                continue
            savings = plugin.tokens_total
            findings.append(
                Finding(
                    rule_id=self.rule_id,
                    severity=self.severity,
                    title=f"'{plugin.name}' likely unused in engineering workflows",
                    evidence=(
                        f"Plugin '{plugin.name}' is enabled and contributes "
                        f"~{savings:,} tokens to the system prompt per turn, "
                        f"but its content area (marketing, finance, regulatory, "
                        f"PM, etc.) doesn't typically apply to coding tasks."
                    ),
                    suggested_action=(
                        f"Disable in ~/.claude/settings.json by setting "
                        f'"{plugin.name}@{plugin.marketplace}": false'
                    ),
                    estimated_savings_tokens=savings,
                    target=plugin.name,
                    metadata={"marketplace": plugin.marketplace},
                )
            )
        return findings
