"""Frozen golden vector for the importer's content-addressed RawEvent (§8/§12c item 5)."""

from __future__ import annotations

import json

from openproof.canonical.encoding import canonical_str
from openproof.ledger.importer import import_session

GOLDEN_ID = "41ba983175acdce003249b2c299f0c80b4ee38b78a0e440578dee01d2b04f6b8"
GOLDEN_LINE = (
    '{"id":"41ba983175acdce003249b2c299f0c80b4ee38b78a0e440578dee01d2b04f6b8",'
    '"kind":"tool_call","nativeAnchor":{"primary":"tu1"},"pairId":"tu1",'
    '"payload":{"input":{"command":"echo hi"},"name":"Bash"},"rawOffsets":[0],'
    '"redactionMarkers":[],"schemaVersion":1,"sessionId":"sess-G",'
    '"source":"claude_jsonl","trust":"HIGH","ts":"2026-06-07T00:00:00.000Z"}'
)

RECORD = [{
    "type": "assistant", "uuid": "a1", "timestamp": "2026-06-07T00:00:00.000Z",
    "message": {"role": "assistant", "content": [
        {"type": "tool_use", "id": "tu1", "name": "Bash", "input": {"command": "echo hi"}}]},
}]


def _import():
    data = ("\n".join(json.dumps(r) for r in RECORD) + "\n").encode("utf-8")
    return import_session("claude_jsonl", "sess-G", data, schema_version=1, file_identity="x")


def test_golden_raw_event_id():
    assert _import().raw_lines[0]["id"] == GOLDEN_ID


def test_golden_raw_event_line_bytes():
    assert canonical_str(_import().raw_lines[0]) == GOLDEN_LINE
