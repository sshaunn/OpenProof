"""Frozen golden vectors for the redaction floor.

Pin the exact redacted bytes, the location-only ``placeholderId``, and the marker span for
a fixed input, so the §6.5 pipeline (traversal → fieldPath → ordinal → placeholderId) is
locked byte-for-byte. A future port must reproduce these.
"""

from __future__ import annotations

from openproof.canonical.encoding import canonical_str
from openproof.redaction import redact

# redact({"cmd": "TUSHARE_TOKEN=abc123"}, source=claude_jsonl, sessionId=s1, recordIndex=0)
GOLDEN_PLACEHOLDER_ID = "d235554fb71510f01ad8b48813efad5982a19b66ec82afdb91a223a239e4de02"
GOLDEN_REDACTED_BYTES = '{"cmd":"TUSHARE_TOKEN=<REDACTED:credential_keyword#0>"}'
GOLDEN_SPAN = (14, 45)  # half-open UTF-8 byte offsets of the placeholder in the field


def _golden():
    return redact({"cmd": "TUSHARE_TOKEN=abc123"}, source="claude_jsonl", session_id="s1", record_index=0)


def test_golden_redacted_bytes():
    assert canonical_str(_golden().payload) == GOLDEN_REDACTED_BYTES


def test_golden_placeholder_id():
    marker = _golden().markers[0]
    assert marker.placeholder_id == GOLDEN_PLACEHOLDER_ID
    assert marker.field_path == "/cmd"
    assert marker.type == "credential_keyword"


def test_golden_span():
    span = _golden().markers[0].span
    assert (span.start_byte, span.end_byte) == GOLDEN_SPAN


def test_no_oracle_golden_is_value_independent():
    # changing only the secret value keeps every committed-facing byte identical
    other = redact({"cmd": "TUSHARE_TOKEN=totallydifferent"}, source="claude_jsonl", session_id="s1", record_index=0)
    assert canonical_str(other.payload) == GOLDEN_REDACTED_BYTES
    assert other.markers[0].placeholder_id == GOLDEN_PLACEHOLDER_ID
