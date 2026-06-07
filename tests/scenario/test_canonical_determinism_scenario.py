"""SCENARIO: the canonical kernel guarantees a reproducible, lossless receipt.

Mirrors the §12c receipt-byte invariant and the §17-task-10 number-domain conformance
story: a second party must be able to recompute the exact bytes/hashes from the ledger
state, distinct source values must never collapse, and over-precision must fail loudly
rather than silently alter a value.
"""

from __future__ import annotations

import pytest

from openproof import canonical
from openproof.canonical.numbers import NumberError, RawNumber


def _state(token_value):
    """A miniature 'committed event core' shaped like a real one."""
    return {
        "schemaVersion": 1,
        "source": "claude_jsonl",
        "sessionId": "sess-1",
        "kind": "tool_result",
        "score": RawNumber(token_value),
    }


def test_same_state_yields_byte_identical_receipt_and_hash():
    # GIVEN two builds of the same logical event state (different key insertion order)
    a = {"b": 1, "score": RawNumber("0.1"), "a": "x"}
    b = {"a": "x", "score": RawNumber("0.1"), "b": 1}

    # THEN the canonical bytes and the content-address are identical
    assert canonical.canonical_bytes(a) == canonical.canonical_bytes(b)
    assert canonical.domain_hash("event-record", a) == canonical.domain_hash("event-record", b)


def test_lossless_big_integers_do_not_collapse():
    # GIVEN two adjacent integers that a binary64 round-trip would merge
    near = canonical.domain_hash("event-record", _state("9007199254740992"))
    far = canonical.domain_hash("event-record", _state("9007199254740993"))

    # THEN they remain distinct in the committed state
    assert near != far


def test_over_precision_fails_loudly_not_silently():
    # GIVEN a non-integer carrying more precision than binary64 can resolve
    # THEN building the canonical bytes REJECTS it (never rounds it away)
    with pytest.raises(NumberError):
        canonical.canonical_bytes(_state("1.0000000000000001"))


def test_supported_values_round_trip_positionally():
    # score sorts between schemaVersion and sessionId, so it is followed by ',"sessionId"'
    assert b'"score":0.0000001,"sessionId"' in canonical.canonical_bytes(_state("1e-7"))
    assert b'"score":0,"sessionId"' in canonical.canonical_bytes(_state("-0.0"))


def test_a_changed_value_changes_the_content_address():
    base = canonical.domain_hash("event-record", _state("0.1"))
    changed = canonical.domain_hash("event-record", _state("0.2"))
    assert base != changed
