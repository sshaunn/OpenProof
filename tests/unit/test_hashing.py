"""Unit tests for §12c domain-tagged SHA-256 framing."""

from __future__ import annotations

import hashlib

import pytest

from openproof.canonical.encoding import canonical_bytes
from openproof.canonical.hashing import DOMAIN_PREFIX, DOMAINS, domain_hash, sha256_hex


def test_framing_matches_manual_canonical_object():
    fields = {"source": "claude_jsonl", "sessionId": "s1"}
    expected = hashlib.sha256(
        canonical_bytes({"domain": DOMAIN_PREFIX + "rawevent-id", **fields})
    ).hexdigest()
    assert domain_hash("rawevent-id", fields) == expected


def test_distinct_domains_never_collide_on_same_fields():
    fields = {"a": 1}
    digests = {domain_hash(kind, fields) for kind in DOMAINS}
    assert len(digests) == len(DOMAINS)  # every domain yields a distinct hash


def test_reserved_domain_member_rejected():
    with pytest.raises(ValueError):
        domain_hash("rawevent-id", {"domain": "x"})


def test_unknown_kind_rejected():
    with pytest.raises(ValueError):
        domain_hash("not-a-real-domain", {})


def test_lowercase_hex_64():
    h = domain_hash("ledger-state", {"x": 1})
    assert len(h) == 64
    assert h == h.lower()
    assert set(h) <= set("0123456789abcdef")


def test_sha256_hex_basic():
    assert sha256_hex(b"") == hashlib.sha256(b"").hexdigest()
