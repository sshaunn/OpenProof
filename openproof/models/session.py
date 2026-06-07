"""Session-level models (§8 ImportedSession, §12a sourceBoundary)."""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["SourceBoundary", "ImportedSession"]


@dataclass(frozen=True)
class SourceBoundary:
    """The FROZEN per-file prefix captured at import start (§12a). LOCAL-ONLY — every field
    (including ``source_prefix_digest_local``, a digest of UNREDACTED bytes) is NEVER
    serialized under ``committed/`` or ``sessions/``; it persists locally so a later import
    can classify a grown prefix and detect an in-place rewrite (P4)."""

    source: str
    session_id: str
    file_identity_local: str
    byte_length_at_open: int
    complete_record_count_at_open: int
    last_complete_record_index: int
    last_complete_native_anchor: str
    source_prefix_digest_local: str


@dataclass(frozen=True)
class ImportedSession:
    """Per-session import summary (§8). The ``unparsedAcknowledged*`` and ``importedAt``
    wall-clock/person fields are display/audit only — excluded from ``ledgerStateHash``."""

    session_id: str
    source: str
    source_version: str | None
    source_record_count: int
    parsed_source_record_count: int
    event_count: int
    known_noise_count: int
    known_noise_counts_by_type: dict
    unparsed_record_count: int
    unparsed_types: tuple[str, ...]
    compaction_boundary_count: int
    thinking_signature_omitted_count: int
    redaction_summary: dict
    imported_at: str | None = None
