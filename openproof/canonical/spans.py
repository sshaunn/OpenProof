"""Half-open UTF-8 byte spans over a field's final NFC-normalized redacted string (§8).

A redaction marker's ``span`` is ``[startByte, endByte)`` — 0-based UTF-8 byte offsets
measured over THAT field's FINAL NFC-normalized redacted string value (not the whole
payload), with ``endByte = startByte + the UTF-8 byte length of the placeholder``.

The byte coordinate is the single pinned unit so two conforming implementations in
different languages compute identical integers (Python str scalar indices, JS/Java
UTF-16 code units, and UTF-8 byte offsets diverge on non-BMP characters). Offsets are
measured AFTER §6.5 redaction and AFTER NFC — so this module normalizes before counting.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

__all__ = ["Span", "nfc", "utf8_len", "byte_offset", "placeholder_span"]


@dataclass(frozen=True)
class Span:
    """A half-open ``[start_byte, end_byte)`` UTF-8 byte interval."""

    start_byte: int
    end_byte: int


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def utf8_len(s: str) -> int:
    """UTF-8 byte length of ``s`` as written (caller NFC-normalizes if required)."""
    return len(s.encode("utf-8"))


def byte_offset(value: str, char_index: int) -> int:
    """UTF-8 byte offset of character position ``char_index`` within ``NFC(value)``."""
    return len(nfc(value)[:char_index].encode("utf-8"))


def placeholder_span(redacted_value: str, char_start: int, placeholder: str) -> Span:
    """Span of ``placeholder`` starting at character ``char_start`` in ``NFC(redacted_value)``.

    ``char_start`` is the character index of the placeholder's first character in the
    final NFC-normalized redacted string; ``endByte`` adds the placeholder's UTF-8 length.
    """
    start = byte_offset(redacted_value, char_start)
    return Span(start, start + utf8_len(placeholder))
