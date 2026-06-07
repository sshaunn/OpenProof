"""The import orchestration (§17 task 4): boundary → normalize → redact → content-address.

Pure transform (``import_session``) + the discovery/IO edges. Each normalized event's
payload is redacted, then content-addressed into a RawEvent; originals go to the vault,
the redacted projection to ``raw/``. Re-import over the same frozen prefix is idempotent.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from ..models.session import ImportedSession
from ..redaction import redact
from ..sources import claude_jsonl
from .boundary import capture_boundary, frozen_prefix
from .projection import build_raw_event, raw_event_line

__all__ = ["ImportOutcome", "import_session"]


@dataclass(frozen=True)
class ImportOutcome:
    session: ImportedSession
    boundary: object
    raw_lines: list
    unredacted_lines: list
    vault_map: dict
    unparsed_records: tuple  # the raw UnparsedRecords (local-only; redacted into the receipt at commit)


def import_session(source: str, session_id: str, data: bytes, *, schema_version: int,
                   file_identity: str, source_version: str | None = None) -> ImportOutcome:
    boundary = capture_boundary(source, session_id, data, file_identity=file_identity)
    records = claude_jsonl.read_records(frozen_prefix(data).decode("utf-8"))
    normalized = claude_jsonl.normalize(records, session_id=session_id)

    # Content-address each event. Claude's append log re-writes the same logical message
    # under one uuid (differing only in incidental metadata), so byte-identical content
    # yields one RawEvent id — DEDUPE to a single line, merging the source record indices
    # into rawOffsets[]. The first (smallest-index) occurrence owns the markers/vault.
    by_id: dict = {}
    unredacted_by_id: dict = {}
    vault_map: dict = {}
    redaction_summary: Counter = Counter()
    for event in normalized.events:
        redaction = redact(event.payload, source=source, session_id=session_id, record_index=event.record_index)
        raw_event = build_raw_event(event, redacted_payload=redaction.payload, markers=redaction.markers, schema_version=schema_version)
        line = raw_event_line(raw_event)
        existing = by_id.get(line["id"])
        if existing is None:
            by_id[line["id"]] = line
            unredacted_by_id[line["id"]] = {"id": line["id"], "payload": event.payload}
            for entry in redaction.vault_entries:
                vault_map[entry.placeholder_id] = {"original": entry.original, "type": entry.type}
                redaction_summary[entry.type] += 1
        else:
            existing["rawOffsets"] = sorted(set(existing["rawOffsets"]) | set(line["rawOffsets"]))

    raw_lines = sorted(by_id.values(), key=lambda line: line["id"])
    unredacted_lines = sorted(unredacted_by_id.values(), key=lambda line: line["id"])

    known_noise_counts = Counter(records[i].get("type") for i in normalized.known_noise_indices)
    session = ImportedSession(
        session_id=session_id,
        source=source,
        source_version=source_version,
        source_record_count=boundary.complete_record_count_at_open,
        parsed_source_record_count=len(normalized.parsed_indices),
        event_count=len(raw_lines),  # distinct content-addressed events (after dedup)
        known_noise_count=len(normalized.known_noise_indices),
        known_noise_counts_by_type=dict(known_noise_counts),
        unparsed_record_count=len(normalized.unparsed_records),
        unparsed_types=tuple(sorted({u.record_type for u in normalized.unparsed_records if u.record_type})),
        compaction_boundary_count=normalized.compaction_boundary_count,
        thinking_signature_omitted_count=normalized.thinking_signature_omitted_count,
        redaction_summary=dict(redaction_summary),
    )
    return ImportOutcome(session, boundary, raw_lines, unredacted_lines, vault_map, normalized.unparsed_records)
