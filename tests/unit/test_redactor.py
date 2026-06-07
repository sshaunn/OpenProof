"""Unit tests for the §6.5 redaction pipeline (traversal, fieldPath, ordinal, overlap)."""

from __future__ import annotations

from openproof.redaction import redact


def r(payload, **kw):
    kw.setdefault("source", "claude_jsonl")
    kw.setdefault("session_id", "s1")
    kw.setdefault("record_index", 0)
    return redact(payload, **kw)


def test_clean_payload_unchanged_no_markers():
    res = r({"msg": "hello world", "n": 5, "b": True, "z": None})
    assert res.markers == ()
    assert res.vault_entries == ()
    assert res.payload == {"msg": "hello world", "n": 5, "b": True, "z": None}


def test_non_string_scalars_pass_through():
    res = r({"i": 5, "f": 1.5, "b": False, "z": None, "s": "token=x"})
    assert res.payload["i"] == 5 and res.payload["f"] == 1.5
    assert res.payload["b"] is False and res.payload["z"] is None
    assert "<REDACTED:" in res.payload["s"]


def test_rfc6901_field_path_escaping():
    # a key containing '/' and '~' must escape to ~1 and ~0 in the JSON-Pointer
    res = r({"a/b~c": "token=secret"})
    assert res.markers[0].field_path == "/a~1b~0c"


def test_array_traversal_and_field_paths():
    res = r({"items": ["token=x", 5, "ghp_" + "c" * 36]})
    paths = sorted(m.field_path for m in res.markers)
    assert paths == ["/items/0", "/items/2"]  # the number at /items/1 is untouched
    assert res.payload["items"][1] == 5


def test_match_ordinal_is_record_local_in_traversal_order():
    # 'a' sorts before 'b' canonically → 'a' gets #0, 'b' gets #1
    res = r({"b": "token=2", "a": "token=1"})
    assert res.payload["a"].endswith("#0>")
    assert res.payload["b"].endswith("#1>")


def test_overlap_resolves_to_single_leftmost_longest_placeholder():
    res = r({"x": "password=scheme://REDACTED_TEST@host"})
    assert len(res.markers) == 1
    assert res.markers[0].type == "credential_keyword"  # outer value span wins


def test_placeholder_id_is_location_only_no_oracle():
    a = r({"cmd": "TUSHARE_TOKEN=secretA"})
    b = r({"cmd": "TUSHARE_TOKEN=secretBBBBBB"})
    assert a.payload == b.payload
    assert a.markers[0].placeholder_id == b.markers[0].placeholder_id


def test_repeated_secret_yields_distinct_placeholder_ids():
    res = r({"a": "token=xyz", "b": "token=xyz"})
    assert len({m.placeholder_id for m in res.markers}) == 2


def test_record_index_changes_placeholder_id():
    a = r({"cmd": "token=x"}, record_index=0)
    b = r({"cmd": "token=x"}, record_index=1)
    assert a.markers[0].placeholder_id != b.markers[0].placeholder_id


def test_marker_span_covers_the_placeholder_bytes():
    res = r({"cmd": "TUSHARE_TOKEN=abc123"})
    marker = res.markers[0]
    redacted = res.payload["cmd"]
    token = f"<REDACTED:{marker.type}#0>"
    assert redacted.encode("utf-8")[marker.span.start_byte:marker.span.end_byte] == token.encode("utf-8")


def test_multiple_placeholders_in_one_field_have_distinct_ascending_spans():
    res = r({"cmd": "export TUSHARE_TOKEN=tok_abc123 && Authorization: Bearer REDACTED.TEST.JWT"})
    assert len(res.markers) == 2
    assert all(m.field_path == "/cmd" for m in res.markers)
    redacted = res.payload["cmd"].encode("utf-8")
    starts = [m.span.start_byte for m in res.markers]
    assert starts == sorted(starts) and len(set(starts)) == 2  # distinct, ascending
    for m in res.markers:  # each span lands on its own placeholder
        assert redacted[m.span.start_byte:m.span.end_byte] == f"<REDACTED:{m.type}#{starts.index(m.span.start_byte)}>".encode()


def test_span_is_utf8_byte_offset_after_non_bmp():
    # a 4-byte emoji before the placeholder → the byte offset exceeds the char index.
    # (the keyword's left boundary is the '_' in TUSHARE_TOKEN; a bare space is NOT a boundary)
    res = r({"cmd": chr(0x1F511) + "TUSHARE_TOKEN=secret"})
    marker = res.markers[0]
    prefix = chr(0x1F511) + "TUSHARE_TOKEN="
    assert marker.span.start_byte == len(prefix.encode("utf-8"))  # 18 bytes
    assert marker.span.start_byte != len(prefix)  # 18 bytes != 15 chars (emoji = 4 bytes / 1 char)


def test_span_locates_real_placeholder_not_a_coincidental_literal():
    # a literal placeholder string in the surrounding text must NOT steal the span
    res = r({"cmd": "<REDACTED:credential_keyword#0> and DB_PASSWORD=hunter2"})
    marker = res.markers[0]
    real_prefix = "<REDACTED:credential_keyword#0> and DB_PASSWORD="
    assert marker.span.start_byte == len(real_prefix.encode("utf-8"))
    redacted = res.payload["cmd"].encode("utf-8")
    assert redacted[marker.span.start_byte:marker.span.end_byte] == b"<REDACTED:credential_keyword#0>"
