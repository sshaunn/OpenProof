"""Canonical projection of a RawEvent (§8/§12c item 5) + the content-addressed id.

The RawEvent ``id`` is a pure function of ``(source, sessionId, nativeAnchor, REDACTED
payload, schemaVersion)`` under the §12c domain-framing rule — ``seq`` excluded — so a
source differing only in a redacted secret value yields the same id (no-oracle). These
projections are reused by the commit snapshot (build-step-6).
"""

from __future__ import annotations

from ..canonical.hashing import domain_hash
from ..models.event import NativeAnchor, NormalizedEvent, RawEvent
from ..models.redaction import RedactionMarker

__all__ = ["anchor_object", "marker_object", "event_id", "raw_event_line", "build_raw_event"]


def anchor_object(anchor: NativeAnchor) -> dict:
    """Canonical nativeAnchor: the bare ``primary`` plus the active ``contentBlockIndex``."""
    obj = {"primary": anchor.primary}
    if anchor.content_block_index is not None:
        obj["contentBlockIndex"] = anchor.content_block_index
    return obj


def marker_object(marker: RedactionMarker) -> dict:
    return {
        "placeholderId": marker.placeholder_id,
        "type": marker.type,
        "fieldPath": marker.field_path,
        "span": [marker.span.start_byte, marker.span.end_byte],
    }


def event_id(source: str, session_id: str, anchor: NativeAnchor, redacted_payload, schema_version: int) -> str:
    return domain_hash(
        "rawevent-id",
        {
            "source": source,
            "sessionId": session_id,
            "nativeAnchor": anchor_object(anchor),
            "payload": redacted_payload,
            "schemaVersion": schema_version,
        },
    )


def raw_event_line(event: RawEvent) -> dict:
    """The redacted RawEvent as a canonical-ready dict (one ``raw/`` line)."""
    line = {
        "id": event.id,
        "schemaVersion": event.schema_version,
        "source": event.source,
        "sessionId": event.session_id,
        "kind": event.kind,
        "ts": event.ts,
        "nativeAnchor": anchor_object(event.native_anchor),
        "payload": event.payload,
        "rawOffsets": list(event.raw_offsets),
        "redactionMarkers": [marker_object(m) for m in event.redaction_markers],
        "trust": event.trust,
    }
    if event.pair_id is not None:
        line["pairId"] = event.pair_id
    return line


def build_raw_event(normalized: NormalizedEvent, *, redacted_payload, markers, schema_version: int) -> RawEvent:
    """Assemble a content-addressed RawEvent from a normalized event + its redaction."""
    return RawEvent(
        id=event_id(normalized.source, normalized.session_id, normalized.native_anchor, redacted_payload, schema_version),
        schema_version=schema_version,
        source=normalized.source,
        session_id=normalized.session_id,
        kind=normalized.kind,
        ts=normalized.ts,
        native_anchor=normalized.native_anchor,
        payload=redacted_payload,
        raw_offsets=(normalized.record_index,),
        redaction_markers=tuple(markers),
        pair_id=normalized.pair_id,
    )
