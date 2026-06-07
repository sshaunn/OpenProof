"""Unit tests for §8 half-open UTF-8 byte spans.

Non-ASCII built with ``chr()`` (pure-ASCII source).
"""

from __future__ import annotations

from openproof.canonical.spans import Span, byte_offset, nfc, placeholder_span, utf8_len

KEY = chr(0x1F511)  # "🔑" — non-BMP, 4 UTF-8 bytes
COMBINING_ACUTE = chr(0x0301)


def test_utf8_len():
    assert utf8_len("abc") == 3
    assert utf8_len(chr(0x00E9)) == 2  # "é" → 2 bytes
    assert utf8_len(KEY) == 4  # non-BMP → 4 bytes


def test_byte_offset_ascii():
    assert byte_offset("abcdef", 3) == 3


def test_byte_offset_after_non_bmp():
    assert byte_offset(KEY + "X", 1) == 4
    assert byte_offset(KEY + "X", 2) == 5


def test_byte_offset_nfc_combining_before_index():
    # "e" + combining acute (2 code points) → NFC "é" (1 code point, 2 bytes)
    assert byte_offset("e" + COMBINING_ACUTE + "X", 1) == 2


def test_placeholder_span_after_non_bmp():
    placeholder = "<REDACTED:credential_keyword_value#0>"
    value = KEY + "X=" + placeholder  # char_start = 3 chars in
    span = placeholder_span(value, 3, placeholder)
    assert span.start_byte == 4 + 1 + 1  # KEY(4) + "X"(1) + "="(1)
    assert span.end_byte == span.start_byte + utf8_len(placeholder)
    assert isinstance(span, Span)


def test_placeholder_span_byte_length_not_char_count():
    # endByte = startByte + the placeholder's UTF-8 BYTE length (§8), not its char count.
    # A multi-byte placeholder distinguishes the two: chr(0x00E9) is 1 char / 2 UTF-8 bytes.
    ph = chr(0x00E9) + "X"  # 2 chars, 3 UTF-8 bytes
    span = placeholder_span("ab" + ph, 2, ph)
    assert span.start_byte == 2  # "ab" → 2 bytes
    assert span.end_byte == 5  # 2 + 3 UTF-8 bytes (NOT 2 + 2 chars == 4)


def test_nfc_idempotent():
    composed = chr(0x00E9)
    assert nfc("e" + COMBINING_ACUTE) == composed
    assert nfc(composed) == composed
