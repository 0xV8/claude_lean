"""Remove stale snapshot sections from memory files, keeping policy/why intact."""

from __future__ import annotations

import re
from pathlib import Path


# Heading patterns that mark a snapshot section (case-insensitive)
_SNAPSHOT_HEADING = re.compile(
    r"^(\*\*)?(setup\s+state|state\s+\(as\s+of|snapshot|installed\s+as\s+of|current\s+state)",
    re.IGNORECASE,
)


def clean_memory_body(text: str) -> tuple[str, bool]:
    """Remove snapshot sections from a memory file's body.

    Returns ``(new_text, changed)``. The frontmatter is preserved untouched.
    """
    if not text.startswith("---\n"):
        return text, False

    end = text.find("\n---\n", 4)
    if end == -1:
        return text, False

    frontmatter = text[: end + 5]
    body = text[end + 5 :]

    new_body, changed = _strip_snapshot_blocks(body)
    if not changed:
        return text, False
    return frontmatter + new_body, True


def clean_memory_file(path: Path) -> bool:
    """In-place clean a memory file. Returns True if anything changed."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    new_text, changed = clean_memory_body(text)
    if not changed:
        return False
    path.write_text(new_text, encoding="utf-8")
    return True


def _strip_snapshot_blocks(body: str) -> tuple[str, bool]:
    """Drop sections that look like dated snapshots."""
    lines = body.splitlines(keepends=True)
    out: list[str] = []
    skipping = False
    changed = False

    for line in lines:
        if skipping:
            # Stop skipping at the next blank-line-then-heading or end of paragraph
            if line.strip() == "":
                # Lookahead would help, but stay simple: treat blank as end of block
                skipping = False
                # Don't emit the blank line (we already consumed the section)
                continue
            # Still in snapshot block; drop
            continue

        # Detect start of snapshot section
        stripped = line.strip()
        if _SNAPSHOT_HEADING.search(stripped):
            skipping = True
            changed = True
            continue

        out.append(line)

    return "".join(out), changed
