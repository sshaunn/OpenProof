"""Component tests for the ``canonical/`` package as an integrated kernel.

Unit tests cover each function; these assert the kernel's emergent guarantees through
its public API: encode↔hash agreement, idempotence, and that distinct logical states
never collapse to identical bytes (the §12c determinism contract the receipt rests on).
"""

from __future__ import annotations

from openproof import canonical


def test_public_api_surface():
    # the kernel exposes exactly its documented building blocks
    for name in ("canonical_bytes", "canonical_str", "domain_hash", "format_number",
                 "RawNumber", "placeholder_span", "nfc", "Span"):
        assert hasattr(canonical, name)


def test_encoding_is_idempotent_and_stable():
    obj = {"z": 1, "a": [3, 2, 1], "m": {"b": 2, "a": 1}}
    first = canonical.canonical_bytes(obj)
    assert canonical.canonical_bytes(obj) == first  # stable across calls
    # re-encoding the decoded-equivalent structure is byte-identical
    assert canonical.canonical_bytes(dict(reversed(list(obj.items())))) == first


def test_hash_is_a_pure_function_of_canonical_bytes():
    fields = {"source": "claude_jsonl", "sessionId": "s", "n": 7}
    import hashlib

    expected = hashlib.sha256(
        canonical.canonical_bytes({"domain": "openproof/v1/event-record", **fields})
    ).hexdigest()
    assert canonical.domain_hash("event-record", fields) == expected


def test_distinct_states_never_collapse():
    # two integers that binary64 would collide must hash differently
    a = canonical.domain_hash("ledger-state", {"n": canonical.RawNumber("9007199254740992")})
    b = canonical.domain_hash("ledger-state", {"n": canonical.RawNumber("9007199254740993")})
    assert a != b


def test_same_logical_state_same_bytes():
    # key order in the source object does not affect committed bytes
    x = canonical.canonical_bytes({"a": 1, "b": 2})
    y = canonical.canonical_bytes({"b": 2, "a": 1})
    assert x == y
