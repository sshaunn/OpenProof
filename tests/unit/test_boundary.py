"""Unit tests for the §12a frozen sourceBoundary capture (LOCAL-ONLY)."""

from __future__ import annotations

from openproof.ledger.boundary import (
    P4_GROWN,
    P4_REWRITTEN,
    P4_SAME,
    capture_boundary,
    compare_boundary,
    frozen_prefix,
    prefix_digest,
)


def test_frozen_prefix_drops_incomplete_final_line():
    assert frozen_prefix(b'{"a":1}\n{"b":2}\n{"partial') == b'{"a":1}\n{"b":2}\n'
    assert frozen_prefix(b"no newline yet") == b""
    assert frozen_prefix(b'{"a":1}\n') == b'{"a":1}\n'


def test_capture_counts_only_complete_records():
    boundary = capture_boundary("claude_jsonl", "s1", b'{"a":1}\n{"b":2}\n{"incomplete', file_identity="local")
    assert boundary.complete_record_count_at_open == 2
    assert boundary.byte_length_at_open == len(b'{"a":1}\n{"b":2}\n')
    assert boundary.last_complete_record_index == 1


def test_capture_records_last_native_anchor():
    data = b'{"type":"user","uuid":"u1"}\n{"type":"assistant","uuid":"a2"}\n'
    boundary = capture_boundary("claude_jsonl", "s1", data, file_identity="local")
    assert boundary.last_complete_native_anchor == "a2"  # the last complete record's anchor


def _anchor(data: bytes) -> str:
    return capture_boundary("c", "s", data, file_identity="x").last_complete_native_anchor


def test_last_native_anchor_degrades_safely():
    assert _anchor(b'{"type":"system"}\n') == ""  # no uuid
    assert _anchor(b"only a partial line, no newline") == ""  # empty frozen prefix
    assert _anchor(b'{"a":1}\nnot json at all\n') == ""  # malformed last complete line
    assert _anchor(b'{"a":1}\n12345\n') == ""  # last complete line is a non-object


def test_prefix_digest_is_byte_sensitive():
    assert prefix_digest(b"abc") == prefix_digest(b"abc")
    assert prefix_digest(b"abc") != prefix_digest(b"abd")


def test_compare_boundary_same_grown_rewritten():
    data = b'{"a":1}\n{"b":2}\n'
    boundary = capture_boundary("claude_jsonl", "s1", data, file_identity="local")
    assert compare_boundary(boundary, data) == P4_SAME
    assert compare_boundary(boundary, data + b'{"c":3}\n') == P4_GROWN
    # an in-place rewrite of the same byte length is detected by the digest
    rewritten = b'{"a":9}\n{"b":2}\n'
    assert compare_boundary(boundary, rewritten) == P4_REWRITTEN
