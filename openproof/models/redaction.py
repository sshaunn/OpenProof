"""Redaction output models (§8 RawEvent.redactionMarkers, §6.5 floor).

A ``RedactionMarker`` is the redacted-side metadata a second party needs to *cite* a
redaction — never to *recover* the secret. Its identity is a pure function of redacted
LOCATION only (``placeholderId``), so two sources differing only in a secret value
produce byte-identical markers (the no-oracle property, §17 task 10). The original
literal lives ONLY in a ``VaultEntry`` (the gitignored, never-tracked vault).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..canonical.spans import Span

__all__ = ["RedactionMarker", "VaultEntry", "RedactionResult"]


@dataclass(frozen=True)
class RedactionMarker:
    """``{placeholderId, type, fieldPath, span}`` — the complete independent-citation key.

    ``field_path`` is the RFC 6901 JSON-Pointer from the payload root to the redacted
    string; ``span`` is the placeholder's half-open ``[startByte, endByte)`` over that
    field's final NFC-normalized redacted string.
    """

    placeholder_id: str
    type: str
    field_path: str
    span: Span


@dataclass(frozen=True)
class VaultEntry:
    """A reversible original → placeholder mapping. LOCAL-ONLY: the ``original`` literal is
    written to ``vault/secrets-map.json`` and is NEVER committed or placed in a marker."""

    placeholder_id: str
    type: str
    original: str


@dataclass(frozen=True)
class RedactionResult:
    """The pure output of redacting one record's payload."""

    payload: object  # same shape as the input; matched spans replaced by disclosed placeholders
    markers: tuple[RedactionMarker, ...]
    vault_entries: tuple[VaultEntry, ...]
