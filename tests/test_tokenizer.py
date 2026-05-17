"""Tests for the tokenizer fallback path."""

from claude_lean.common.tokenizer import count_tokens, accuracy_label, is_exact


def test_empty_string_is_zero():
    assert count_tokens("") == 0


def test_non_empty_has_positive_count():
    assert count_tokens("hello world") > 0


def test_byte_based_approximation_is_proportional():
    # In approximate mode, doubling the input roughly doubles the count.
    # With tiktoken installed, it's exact and tighter but still proportional.
    short = "hello world"
    long_text = "hello world" * 100
    short_count = count_tokens(short)
    long_count = count_tokens(long_text)
    # long is 100x; expect at least 50x more tokens (loose bound for either mode)
    assert long_count >= short_count * 50


def test_accuracy_label_is_string():
    label = accuracy_label()
    assert isinstance(label, str)
    assert "exact" in label or "approximate" in label


def test_is_exact_returns_bool():
    assert isinstance(is_exact(), bool)
