"""Unit tests for the RawEvent projection + content-addressed id (§8/§12c item 5)."""

from __future__ import annotations

from openproof.canonical.spans import Span
from openproof.ledger.projection import anchor_object, event_id, marker_object, raw_event_line
from openproof.models.event import NativeAnchor, NormalizedEvent
from openproof.models.redaction import RedactionMarker


def test_anchor_object_omits_absent_sub_anchor():
    assert anchor_object(NativeAnchor("u1")) == {"primary": "u1"}
    assert anchor_object(NativeAnchor("u1", 2)) == {"primary": "u1", "contentBlockIndex": 2}


def test_marker_object_shape():
    marker = RedactionMarker("pid", "credential_keyword", "/cmd", Span(3, 9))
    assert marker_object(marker) == {
        "placeholderId": "pid", "type": "credential_keyword", "fieldPath": "/cmd", "span": [3, 9],
    }


def test_event_id_excludes_value_and_record_index_no_oracle():
    # the id is a pure function of (source, sessionId, nativeAnchor, REDACTED payload, schemaVersion)
    anchor = NativeAnchor("u1")
    a = event_id("claude_jsonl", "s", anchor, {"text": "<REDACTED:credential_keyword#0>"}, 1)
    b = event_id("claude_jsonl", "s", anchor, {"text": "<REDACTED:credential_keyword#0>"}, 1)
    assert a == b  # deterministic; record index is not an input (idempotent re-import)


def test_event_id_changes_with_payload():
    anchor = NativeAnchor("u1")
    assert event_id("claude_jsonl", "s", anchor, {"text": "a"}, 1) != event_id("claude_jsonl", "s", anchor, {"text": "b"}, 1)


def test_raw_event_line_includes_pair_id_only_when_present():
    from openproof.ledger.projection import build_raw_event

    ev = NormalizedEvent("tool_call", "claude_jsonl", "s", 0, NativeAnchor("tu1"), {"name": "Bash"}, "TS", "tu1")
    line = raw_event_line(build_raw_event(ev, redacted_payload={"name": "Bash"}, markers=(), schema_version=1))
    assert line["pairId"] == "tu1"
    assert line["kind"] == "tool_call" and line["rawOffsets"] == [0] and line["trust"] == "HIGH"

    prompt = NormalizedEvent("prompt", "claude_jsonl", "s", 0, NativeAnchor("u1"), {"content": "hi"}, "TS", None)
    pline = raw_event_line(build_raw_event(prompt, redacted_payload={"content": "hi"}, markers=(), schema_version=1))
    assert "pairId" not in pline
