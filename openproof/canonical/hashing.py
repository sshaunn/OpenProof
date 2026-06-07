"""Domain-tagged SHA-256 framing (§12c).

Every SHA-256 in the spec is ``SHA-256(canonical(OBJ))`` where ``OBJ`` is the named
field map for that hash with a reserved ``domain`` member set to the hash's constant
domain string. This is the ONE framing operator — no bare prefix concatenation, no
separator, no length-prefix — so inputs are unambiguously framed and there is no second
byte-format to pin. Distinct domains keep otherwise-identical inputs from colliding
across hash kinds (e.g. a RawEvent ``id`` vs its ``eventRecordHash``).
"""

from __future__ import annotations

import hashlib

from .encoding import canonical_bytes

__all__ = ["DOMAIN_PREFIX", "DOMAINS", "sha256_hex", "domain_hash"]

DOMAIN_PREFIX = "openproof/v1/"

# The complete frozen set of §12c hash kinds. Anything else is a programming error.
DOMAINS = frozenset(
    {
        "rawevent-id",
        "event-record",
        "placeholder-id",
        "opaque-id",
        "redacted-record",
        "redacted-payload",
        "ledger-state",
        "source-prefix-local",
    }
)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def domain_hash(kind: str, fields: dict) -> str:
    """``SHA-256(canonical({"domain": "openproof/v1/<kind>", **fields}))`` as lowercase hex."""
    if kind not in DOMAINS:
        raise ValueError(f"unknown hash domain kind: {kind!r}")
    if "domain" in fields:
        raise ValueError("'domain' is the reserved framing member and cannot be a field")
    return sha256_hex(canonical_bytes({"domain": DOMAIN_PREFIX + kind, **fields}))
