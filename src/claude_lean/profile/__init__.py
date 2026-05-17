"""Profile subsystem: swappable per-project context configurations."""

from claude_lean.profile.schema import Profile
from claude_lean.profile.manager import ProfileManager

__all__ = ["Profile", "ProfileManager"]
