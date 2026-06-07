"""Frozen golden hash + canonical-byte vectors.

These pin the exact bytes the §12c ``canonical(...)`` procedure produces and the exact
domain-tagged digests over them. They lock implementation details the spec delegates —
in particular that a hash input is the value's canonical bytes with **no trailing
newline** (the LF terminators are a file-format concern, applied by file writers). A
future Rust/Go port must reproduce these digests byte-for-byte.
"""

from __future__ import annotations

from openproof.canonical.encoding import canonical_bytes
from openproof.canonical.hashing import DOMAIN_PREFIX, DOMAINS, domain_hash

# A representative object exercising sorting, nesting, an array, and a bignum.
GOLDEN_OBJECT = {"b": [3, 1, 2], "a": 1, "n": 9007199254740993}
GOLDEN_OBJECT_BYTES = b'{"a":1,"b":[3,1,2],"n":9007199254740993}'

# Domain-tagged digests over fixed inputs (lowercase hex).
GOLDEN_HASHES = {
    ("rawevent-id", (("source", "claude_jsonl"), ("sessionId", "s1"))):
        "13550416f0a6c0091a05baa317f37f275555fbf2db7c65267c95d2493718c3c7",
    ("event-record", (("source", "claude_jsonl"), ("sessionId", "s1"))):
        "78e09d1ce8ade7c594c282634596d865b83892550982187f3904c7ada8c27daf",
    ("ledger-state", (("x", 1),)):
        "82a986c2151a0168aaafec32a793ac6ff1dd6bbb8d16c07a24bc6cfa3f54f352",
}


def test_canonical_bytes_golden():
    assert canonical_bytes(GOLDEN_OBJECT) == GOLDEN_OBJECT_BYTES


def test_domain_hash_golden_vectors():
    for (kind, items), expected in GOLDEN_HASHES.items():
        assert domain_hash(kind, dict(items)) == expected


def test_same_fields_different_domain_diverge_in_vectors():
    rawevent = GOLDEN_HASHES[("rawevent-id", (("source", "claude_jsonl"), ("sessionId", "s1")))]
    event_record = GOLDEN_HASHES[("event-record", (("source", "claude_jsonl"), ("sessionId", "s1")))]
    assert rawevent != event_record  # identical fields, distinct domain tag


# Hardcoded golden digests over {"x": 1} for every previously-unpinned domain tag,
# computed INDEPENDENTLY (standalone hashlib, not via DOMAIN_PREFIX + kind), so a mistyped
# tag or a changed prefix in the implementation is caught here, not masked. A future port
# must reproduce these byte-for-byte.
GOLDEN_DOMAIN_DIGESTS_OVER_X1 = {
    "placeholder-id": "20ef6b6a6f83aa7c03cecbb501919a9599748a459cd2399e4d4ce070a165aeff",
    "opaque-id": "7040c731289fbcc7778cd5e20a41eda4a701c54304971a302dc180fd083098bc",
    "redacted-record": "193a613dd83cc2c83ecbc872c9e989f774523123e08ca1894cf4f1f7fbb48e06",
    "redacted-payload": "a59dcf80fe1ce1d3e1acfad7257e335dcb031090dff846fe057c0365a1b9505b",
    "source-prefix-local": "5c686227e00a4ce67f2dafdf9fa52d2f7f9e9339529eb7c2e6163fbb2fd79b3f",
}


def test_domain_prefix_and_set_are_frozen():
    assert DOMAIN_PREFIX == "openproof/v1/"
    assert sorted(DOMAINS) == [
        "event-record",
        "ledger-state",
        "opaque-id",
        "placeholder-id",
        "rawevent-id",
        "redacted-payload",
        "redacted-record",
        "source-prefix-local",
    ]


def test_every_domain_tag_string_is_pinned():
    import hashlib

    for kind in DOMAINS:
        expected = hashlib.sha256(
            canonical_bytes({"domain": "openproof/v1/" + kind, "x": 1})
        ).hexdigest()
        assert domain_hash(kind, {"x": 1}) == expected
    # and a hardcoded golden for each previously-unpinned tag (catches a changed prefix)
    for kind, expected_hex in GOLDEN_DOMAIN_DIGESTS_OVER_X1.items():
        assert domain_hash(kind, {"x": 1}) == expected_hex
