"""The ``.openproof/`` file store (§9). Writes the gitignored, never-tracked surfaces:
the redacted ``raw/`` projection (the citation target), the ``vault/`` originals, and the
tracked per-session summary. All bytes go through the one canonical encoding."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from ..canonical.encoding import canonical_bytes
from ..config import Layout
from ..models.session import ImportedSession, SourceBoundary

__all__ = ["session_to_dict", "write_session", "read_raw_lines", "write_boundary", "read_boundary",
           "read_unparsed", "iter_sessions"]


def session_to_dict(session: ImportedSession) -> dict:
    return {
        "sessionId": session.session_id,
        "source": session.source,
        "sourceVersion": session.source_version,
        "sourceRecordCount": session.source_record_count,
        "parsedSourceRecordCount": session.parsed_source_record_count,
        "eventCount": session.event_count,
        "knownNoiseCount": session.known_noise_count,
        "knownNoiseCountsByType": session.known_noise_counts_by_type,
        "unparsedRecordCount": session.unparsed_record_count,
        "unparsedTypes": list(session.unparsed_types),
        "compactionBoundaryCount": session.compaction_boundary_count,
        "thinkingSignatureOmittedCount": session.thinking_signature_omitted_count,
        "redactionSummary": session.redaction_summary,
    }


def _jsonl(dicts) -> bytes:
    return b"".join(canonical_bytes(d) + b"\n" for d in dicts)


def write_session(layout: Layout, source: str, session_id: str, *, raw_lines, unredacted_lines,
                  vault_map, session, unparsed_records=()) -> None:
    raw_path = layout.raw / source / f"{session_id}.jsonl"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(_jsonl(raw_lines))

    # surfaced unknown records (local-only, gitignored; redacted into the receipt at commit)
    unparsed_path = layout.raw / "_unparsed" / source / f"{session_id}.jsonl"
    unparsed_path.parent.mkdir(parents=True, exist_ok=True)
    unparsed_path.write_bytes(_jsonl(
        {"recordIndex": u.record_index, "recordType": u.record_type, "recordSubtype": u.record_subtype, "raw": u.raw}
        for u in unparsed_records
    ))

    mirror = layout.vault / "raw-unredacted" / source / f"{session_id}.jsonl"
    mirror.parent.mkdir(parents=True, exist_ok=True)
    mirror.write_bytes(_jsonl(unredacted_lines))

    if vault_map:
        secrets = layout.vault / "secrets-map.json"
        secrets.parent.mkdir(parents=True, exist_ok=True)
        existing = json.loads(secrets.read_text(encoding="utf-8")) if secrets.exists() else {}
        existing.update(vault_map)
        secrets.write_bytes(canonical_bytes(existing) + b"\n")

    sess_path = layout.sessions / f"{source}-{session_id}.yml"
    sess_path.parent.mkdir(parents=True, exist_ok=True)
    sess_path.write_bytes(canonical_bytes(session_to_dict(session)) + b"\n")


def read_raw_lines(layout: Layout, source: str, session_id: str) -> bytes:
    raw_path = layout.raw / source / f"{session_id}.jsonl"
    return raw_path.read_bytes() if raw_path.exists() else b""


def _read_jsonl(path: Path) -> list:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_unparsed(layout: Layout, source: str, session_id: str) -> list:
    """The local-only surfaced unknown records for a session (read at commit time)."""
    return _read_jsonl(layout.raw / "_unparsed" / source / f"{session_id}.jsonl")


def iter_sessions(layout: Layout):
    """Yield ``(source, session_id)`` for every imported session, from sessions/*.yml."""
    if not layout.sessions.exists():
        return
    for path in sorted(layout.sessions.glob("*.yml")):
        summary = json.loads(path.read_text(encoding="utf-8"))
        yield summary["source"], summary["sessionId"]


def _boundary_path(layout: Layout, source: str, session_id: str) -> Path:
    return layout.boundaries / f"{source}-{session_id}.json"


def write_boundary(layout: Layout, boundary: SourceBoundary) -> None:
    """Persist the LOCAL-ONLY frozen boundary (§12a: it MUST persist between imports so a
    later import can classify a grown prefix / detect a rewrite). Under gitignored raw/."""
    path = _boundary_path(layout, boundary.source, boundary.session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(dataclasses.asdict(boundary)) + b"\n")


def read_boundary(layout: Layout, source: str, session_id: str) -> SourceBoundary | None:
    path = _boundary_path(layout, source, session_id)
    return SourceBoundary(**json.loads(path.read_text(encoding="utf-8"))) if path.exists() else None
