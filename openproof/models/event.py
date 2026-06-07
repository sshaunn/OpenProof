"""The normalized event model (§6 item 2/3, §8).

A ``NormalizedEvent`` is the source-agnostic, pre-redaction, pre-id event the normalizer
produces. The importer (build-step-4) redacts its payload and computes the content-
addressed RawEvent ``id``. ``kind ∈ prompt|assistant_msg|tool_call|tool_result|meta``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .redaction import RedactionMarker

__all__ = ["NativeAnchor", "NormalizedEvent", "UnparsedRecord", "NormalizeResult", "RawEvent"]


@dataclass(frozen=True)
class NativeAnchor:
    """``uuid | tool_use_id`` plus the §8 active ``contentBlockIndex`` sub-anchor.

    ``content_block_index`` is set only when the source record emits MORE THAN ONE
    block-derived event (so a thinking ``assistant_msg`` and a co-located text
    ``assistant_msg`` can never collide on ``id``); ``None`` otherwise.
    """

    primary: str
    content_block_index: int | None = None


@dataclass(frozen=True)
class NormalizedEvent:
    kind: str
    source: str
    session_id: str
    record_index: int
    native_anchor: NativeAnchor
    payload: object
    ts: str | None = None
    pair_id: str | None = None  # tool_use_id linking tool_call ↔ tool_result


@dataclass(frozen=True)
class UnparsedRecord:
    """An unknown source record routed to ``raw/_unparsed/`` — never dropped."""

    record_index: int
    record_type: str | None
    record_subtype: str | None
    raw: object  # the source record; the commit step redacts it recursively + strips paths


@dataclass(frozen=True)
class NormalizeResult:
    events: tuple[NormalizedEvent, ...]
    parsed_indices: frozenset
    known_noise_indices: frozenset
    unparsed_records: tuple[UnparsedRecord, ...]
    compaction_boundary_count: int
    thinking_signature_omitted_count: int


@dataclass(frozen=True)
class RawEvent:
    """A normalized, REDACTED, content-addressed event — the citeable ledger spine (§8/§11).

    ``id`` is a pure function of ``(source, sessionId, nativeAnchor, redacted payload,
    schemaVersion)`` (``seq`` excluded), so re-import is idempotent. ``payload`` is the
    redacted projection; the original lives only in the vault.
    """

    id: str
    schema_version: int
    source: str
    session_id: str
    kind: str
    ts: str | None
    native_anchor: NativeAnchor
    payload: object
    raw_offsets: tuple[int, ...]  # source-relative record indices only (never a path/byte range)
    redaction_markers: tuple[RedactionMarker, ...] = ()
    pair_id: str | None = None
    trust: str = "HIGH"
