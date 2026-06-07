"""The one frozen canonical output encoding (§12c).

A single encoding governs BOTH every hash input AND every committed file byte, so the
hash and the receipt files are byte-identical across machines, OSes, and conforming
implementations:

  * UTF-8 with NFC normalization applied to every key and string value BEFORE sorting;
    if NFC makes two sibling keys collide the encode FAILS (never silent merge/last-wins);
  * object keys sorted lexicographically by Unicode code point at every level
    (deliberately code point, NOT UTF-16 code units like RFC 8785 JCS);
  * arrays are emitted in the given order — the CALLER pre-sorts by the §12c stated key;
  * strings minimally escaped, non-ASCII emitted as raw UTF-8 (no ``\\u`` escapes, no
    slash escaping);
  * numbers under the §12c lossless numeric domain (see :mod:`.numbers`);
  * non-finite numbers REJECTED.

``canonical_bytes(obj)`` is the ``canonical(...)`` procedure used by every SHA-256 in
the spec; it carries NO trailing newline (the LF line/file terminators are applied by
the file writers, not by a value's canonical form).
"""

from __future__ import annotations

import unicodedata

from .numbers import RawNumber, format_number

__all__ = ["CanonicalEncodingError", "canonical_str", "canonical_bytes"]


class CanonicalEncodingError(ValueError):
    """A value cannot be canonically encoded (bad type or an NFC key collision)."""


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


_SHORT_ESCAPES = {
    '"': '\\"',
    "\\": "\\\\",
    "\b": "\\b",
    "\f": "\\f",
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
}


def _encode_str(s: str) -> str:
    parts = ['"']
    for ch in _nfc(s):
        short = _SHORT_ESCAPES.get(ch)
        if short is not None:
            parts.append(short)
        elif ch < "\x20":
            parts.append(f"\\u{ord(ch):04x}")
        else:
            parts.append(ch)  # raw UTF-8: all non-ASCII and '/' pass through
    parts.append('"')
    return "".join(parts)


def _encode_obj(obj: dict) -> str:
    normalized: dict[str, object] = {}
    for key, val in obj.items():
        if not isinstance(key, str):
            raise CanonicalEncodingError(f"non-string object key: {key!r}")
        nkey = _nfc(key)
        if nkey in normalized:
            raise CanonicalEncodingError(f"NFC normalization collides sibling key: {nkey!r}")
        normalized[nkey] = val
    members = (
        f"{_encode_str(k)}:{_encode(v)}"
        for k, v in sorted(normalized.items(), key=lambda kv: kv[0])
    )
    return "{" + ",".join(members) + "}"


# value-kind → encoder; booleans/None handled by identity checks first (bool ⊂ int).
def _encode(value: object) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return _encode_str(value)
    if isinstance(value, (RawNumber, int, float)):
        return format_number(value)
    if isinstance(value, dict):
        return _encode_obj(value)
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_encode(v) for v in value) + "]"
    raise CanonicalEncodingError(f"non-encodable type: {type(value).__name__}")


def canonical_str(value: object) -> str:
    """Canonical text of a single value (no trailing newline)."""
    return _encode(value)


def canonical_bytes(value: object) -> bytes:
    """Canonical UTF-8 bytes of a single value — the ``canonical(...)`` of every hash."""
    return canonical_str(value).encode("utf-8")
