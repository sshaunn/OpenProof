"""Component tests for the redactor over realistic nested payloads."""

from __future__ import annotations

from openproof.canonical.encoding import canonical_str
from openproof.redaction import redact


def r(payload, **kw):
    kw.setdefault("source", "claude_jsonl")
    kw.setdefault("session_id", "s1")
    kw.setdefault("record_index", 3)
    return redact(payload, **kw)


def test_realistic_tool_use_payload():
    payload = {
        "name": "Bash",
        "tool_input": {
            "command": "export TUSHARE_TOKEN=tok_abc123 && curl -H 'Authorization: Bearer REDACTED.TEST.JWT'",
            "description": "set up the API client",
        },
        "metadata": {"total_tokens": 512},  # a non-secret that must survive
    }
    res = r(payload)
    # two secrets redacted (the token value + the bearer/jwt), the non-secret untouched
    assert len(res.markers) == 2
    assert res.payload["metadata"]["total_tokens"] == 512
    assert res.payload["tool_input"]["description"] == "set up the API client"
    serialized = canonical_str(res.payload)
    assert "tok_abc123" not in serialized
    assert "REDACTED.TEST.JWT" not in serialized


def test_vault_holds_originals_markers_do_not():
    res = r({"cmd": "TUSHARE_TOKEN=supersecret"})
    # the marker carries no recoverable literal
    marker = res.markers[0]
    assert "supersecret" not in (marker.placeholder_id + marker.type + marker.field_path)
    # the vault is the single home for the original, keyed by the same placeholderId
    vault = {v.placeholder_id: v.original for v in res.vault_entries}
    assert vault[marker.placeholder_id] == "supersecret"


def test_redaction_is_deterministic():
    payload = {"a": "sk-" + "Z" * 30, "b": ["token=1", "ghp_" + "y" * 36]}
    first = r(payload)
    second = r(payload)
    assert canonical_str(first.payload) == canonical_str(second.payload)
    assert [m.placeholder_id for m in first.markers] == [m.placeholder_id for m in second.markers]


def test_zero_matched_literal_survives_in_payload_or_markers():
    secrets = {
        "pem": "-----BEGIN REDACTED TEST BLOCK-----\nMIIabc\n-----END REDACTED TEST BLOCK-----",
        "sk": "sk-" + "Q" * 32,
        "bearer": "Bearer REDACTED_TEST",
        "conn": "scheme://REDACTED_TEST@cache:6379",
        "cred": "DB_PASSWORD=p@ssw0rd",
    }
    res = r(secrets)
    blob = canonical_str(res.payload) + "".join(m.placeholder_id + m.field_path for m in res.markers)
    for original in (v.original for v in res.vault_entries):
        assert original not in blob
