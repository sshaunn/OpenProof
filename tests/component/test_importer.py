"""Component tests for the importer (boundary → normalize → redact → content-address)."""

from __future__ import annotations

import json

from openproof.canonical.encoding import canonical_bytes
from openproof.ledger.importer import import_session


def _jsonl(records) -> bytes:
    return ("\n".join(json.dumps(r) for r in records) + "\n").encode("utf-8")


def _records():
    return [
        {"type": "user", "uuid": "u1", "timestamp": "TS", "message": {"role": "user", "content": "run it"}},
        {"type": "assistant", "uuid": "a1", "timestamp": "TS", "message": {"role": "assistant", "content": [
            {"type": "tool_use", "id": "tu1", "name": "Bash", "input": {"command": "export TUSHARE_TOKEN=secret123"}},
        ]}},
    ]


def test_import_redacts_and_content_addresses():
    out = import_session("claude_jsonl", "s1", _jsonl(_records()), schema_version=1, file_identity="local")
    assert len(out.raw_lines) == 2
    # the secret is redacted in raw/, the original is in the vault only
    blob = b"".join(canonical_bytes(line) + b"\n" for line in out.raw_lines)
    assert b"secret123" not in blob
    assert any(v["original"] == "secret123" for v in out.vault_map.values())
    assert out.session.redaction_summary == {"credential_keyword": 1}


def test_ids_are_unique_and_sorted():
    out = import_session("claude_jsonl", "s1", _jsonl(_records()), schema_version=1, file_identity="local")
    ids = [line["id"] for line in out.raw_lines]
    assert len(ids) == len(set(ids))
    assert ids == sorted(ids)


def test_duplicate_records_dedupe_with_merged_offsets():
    # the same logical message written twice (Claude append-log retry) → one event, two offsets
    records = _records() + [dict(_records()[1], slug="retry")]  # a3rd record == a1 content + extra metadata
    out = import_session("claude_jsonl", "s1", _jsonl(records), schema_version=1, file_identity="local")
    assert len(out.raw_lines) == 2  # not 3 — the duplicate assistant record deduped
    tool_call = next(line for line in out.raw_lines if line["kind"] == "tool_call")
    assert tool_call["rawOffsets"] == [1, 2]  # both source indices recorded
    assert out.session.event_count == 2
    # the duplicate's redaction is NOT double-counted: the first occurrence owns the vault/summary
    assert out.session.redaction_summary == {"credential_keyword": 1}
    assert len(out.vault_map) == 1


def test_partial_trailing_line_excluded_by_importer():
    # the importer wires the frozen boundary: a partial trailing JSON line (no newline) is
    # ignored — not counted in sourceRecordCount and not normalized into an event
    complete = json.dumps(_records()[0])
    data = (complete + "\n" + '{"type":"user","uuid":"PARTIAL"').encode("utf-8")  # no closing newline
    out = import_session("claude_jsonl", "s1", data, schema_version=1, file_identity="local")
    assert out.session.source_record_count == 1
    assert all("PARTIAL" not in str(line) for line in out.raw_lines)


def test_reimport_is_byte_identical():
    data = _jsonl(_records())
    a = import_session("claude_jsonl", "s1", data, schema_version=1, file_identity="local")
    b = import_session("claude_jsonl", "s1", data, schema_version=1, file_identity="local")
    serialize = lambda out: b"".join(canonical_bytes(line) + b"\n" for line in out.raw_lines)
    assert serialize(a) == serialize(b)


def test_partition_counts_recorded():
    records = _records() + [{"type": "attachment", "uuid": "n1"}, {"type": "system", "subtype": "x"}]
    out = import_session("claude_jsonl", "s1", _jsonl(records), schema_version=1, file_identity="local")
    s = out.session
    assert s.source_record_count == 4
    assert s.known_noise_count == 1 and s.known_noise_counts_by_type == {"attachment": 1}
    assert s.unparsed_record_count == 1 and s.unparsed_types == ("system",)
    # P2 partition arithmetic recomputable from the summary
    assert s.parsed_source_record_count + s.known_noise_count + s.unparsed_record_count == s.source_record_count
