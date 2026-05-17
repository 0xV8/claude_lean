"""Audit subsystem: read-only inspection of ~/.claude/."""

from claude_lean.audit.scanner import scan
from claude_lean.audit.analyzer import analyze
from claude_lean.audit.report import render_terminal, render_json

__all__ = ["scan", "analyze", "render_terminal", "render_json"]
