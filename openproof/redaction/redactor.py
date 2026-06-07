"""The single frozen redaction pipeline (§6.5(1)-(4)).

For one record's normalized payload:
  (1) traverse strings in CANONICAL order — object keys NFC-normalized then sorted by
      Unicode code point, array elements in index order, depth-first;
  (2) ``canonicalFieldPath`` = the RFC 6901 JSON-Pointer to each redacted string;
  (3) within each string, take the LEFTMOST-LONGEST cover of all family matches under the
      fixed family precedence;
  (4) assign ``matchOrdinal`` to the surviving spans, record-local, in
      canonical-traversal-then-span-offset order, starting at 0 (AFTER overlap elimination).

``placeholderId`` is a pure function of redacted LOCATION only — the original literal, the
vault's contents, and import order are never inputs — so two sources differing only in a
secret value produce byte-identical placeholders/payload (the no-oracle property).
"""

from __future__ import annotations

import unicodedata

from ..canonical.hashing import domain_hash
from ..canonical.spans import Span, nfc, utf8_len
from ..models.redaction import RedactionMarker, RedactionResult, VaultEntry
from .patterns import FAMILIES

__all__ = ["redact"]


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def _escape(token: str) -> str:
    """RFC 6901 reference-token escaping: ``~`` → ``~0``, ``/`` → ``~1``."""
    return token.replace("~", "~0").replace("/", "~1")


def _pointer(parent: str, key: str) -> str:
    return parent + "/" + _escape(_nfc(key))


def _walk(value, pointer: str = ""):
    """Yield ``(json_pointer, string)`` for every string in canonical traversal order."""
    if isinstance(value, str):
        yield pointer, value
    elif isinstance(value, dict):
        for nkey, key in sorted(((_nfc(k), k) for k in value), key=lambda p: p[0]):
            yield from _walk(value[key], pointer + "/" + _escape(nkey))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            yield from _walk(item, pointer + "/" + str(index))


def _rebuild(value, replacements: dict, pointer: str = ""):
    """Reconstruct ``value`` with redacted strings substituted at their pointers."""
    if isinstance(value, str):
        return replacements.get(pointer, value)
    if isinstance(value, dict):
        return {k: _rebuild(value[k], replacements, _pointer(pointer, k)) for k in value}
    if isinstance(value, (list, tuple)):
        return [_rebuild(v, replacements, pointer + "/" + str(i)) for i, v in enumerate(value)]
    return value


def _resolve(matches: list) -> list:
    """Leftmost-longest cover of ``(start, end, type, precedence)`` matches; precedence
    breaks ties on equal spans. Returns accepted ``(start, end, type)`` sorted by start."""
    accepted: list = []
    for start, end, type_, _prec in sorted(matches, key=lambda m: (m[0], -(m[1] - m[0]), m[3])):
        if all(end <= a[0] or start >= a[1] for a in accepted):
            accepted.append((start, end, type_))
    return sorted(accepted, key=lambda a: a[0])


def redact(payload, *, source: str, session_id: str, record_index: int) -> RedactionResult:
    """Redact one record's payload; pure (no I/O), deterministic, no-oracle."""
    ordinal = 0
    markers: list[RedactionMarker] = []
    vault: list[VaultEntry] = []
    replacements: dict[str, str] = {}

    for pointer, text in _walk(payload):
        candidates = [
            (start, end, fam.type, fam.precedence)
            for fam in FAMILIES
            for (start, end) in fam.find(text)
            if start < end
        ]
        accepted = _resolve(candidates)
        if not accepted:
            continue

        # (4) assign record-local ordinals in span-offset order; build placeholders
        planned = []  # (start, end, token, type, placeholder_id, original)
        for start, end, type_ in accepted:
            placeholder_id = domain_hash(
                "placeholder-id",
                {
                    "source": source,
                    "sessionId": session_id,
                    "recordIndex": record_index,
                    "canonicalFieldPath": pointer,
                    "matchOrdinal": ordinal,
                    "redactionType": type_,
                },
            )
            planned.append((start, end, f"<REDACTED:{type_}#{ordinal}>", type_, placeholder_id, text[start:end]))
            ordinal += 1

        # build the redacted string left-to-right, recording each placeholder's OWN start
        # offset — never re-find() the token, since a coincidental literal placeholder in the
        # surrounding non-secret text would otherwise mislocate the span.
        parts: list[str] = []
        cursor = running = 0
        token_char_start: dict[str, int] = {}
        for start, end, token, *_ in sorted(planned, key=lambda p: p[0]):
            prefix = text[cursor:start]
            parts.append(prefix)
            running += len(prefix)
            token_char_start[token] = running
            parts.append(token)
            running += len(token)
            cursor = end
        parts.append(text[cursor:])
        redacted = "".join(parts)
        replacements[pointer] = redacted

        # span = the placeholder's own [startByte, endByte) over the FINAL NFC redacted string.
        # The placeholder begins with ASCII '<' (a non-combining starter), so NFC of the prefix
        # is independent of what follows — utf8_len(nfc(prefix)) is the exact startByte.
        for start, end, token, type_, placeholder_id, original in planned:
            start_byte = utf8_len(nfc(redacted[: token_char_start[token]]))
            span = Span(start_byte, start_byte + utf8_len(token))
            markers.append(RedactionMarker(placeholder_id, type_, pointer, span))
            vault.append(VaultEntry(placeholder_id, type_, original))

    return RedactionResult(_rebuild(payload, replacements), tuple(markers), tuple(vault))
