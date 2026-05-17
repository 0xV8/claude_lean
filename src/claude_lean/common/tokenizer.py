"""Token counting with a clean fallback path.

We try tiktoken (Anthropic-family tokenizer family, ``cl100k_base``) for
exact counts. If not installed, we fall back to a byte-based heuristic
that is "close enough" for ranking purposes: most text-mode tokenizers
average ~4 bytes per token on English/code prose.

The fallback's exact ratio is configurable so users who want a better
approximation for their content can override it.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

# Mean bytes per token for English+code prose. Empirical, conservative.
DEFAULT_BYTES_PER_TOKEN = 4.0


@lru_cache(maxsize=1)
def _tiktoken_encoder():
    """Lazily import tiktoken; return None if unavailable."""
    try:
        import tiktoken  # type: ignore
        return tiktoken.get_encoding("cl100k_base")
    except (ImportError, Exception):
        return None


def count_tokens(text: str, *, bytes_per_token: float = DEFAULT_BYTES_PER_TOKEN) -> int:
    """Count tokens in a string.

    Uses tiktoken if installed (exact); otherwise a byte-based estimate
    (approximate within ~15% for typical prose/code).
    """
    if not text:
        return 0
    enc = _tiktoken_encoder()
    if enc is not None:
        return len(enc.encode(text))
    return max(1, int(len(text.encode("utf-8")) / bytes_per_token))


def count_file_tokens(path: Path, *, bytes_per_token: float = DEFAULT_BYTES_PER_TOKEN) -> int:
    """Count tokens for a file's contents."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    return count_tokens(text, bytes_per_token=bytes_per_token)


def is_exact() -> bool:
    """True if tiktoken is available and counts will be exact."""
    return _tiktoken_encoder() is not None


def accuracy_label() -> str:
    """Human-readable label for the current accuracy mode."""
    return "exact (tiktoken)" if is_exact() else "approximate (byte-based)"
