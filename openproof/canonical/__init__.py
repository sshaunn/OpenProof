"""The deterministic kernel — pure, no I/O, no clock, no randomness (plan §2/§4).

Everything under ``canonical/`` is exhaustively golden-tested; it is the single home
of the §12c canonical encoding, the lossless numeric domain, domain-tagged hashing,
and UTF-8 byte spans. Nothing here imports anything from a layer above it.
"""

from __future__ import annotations

from .encoding import CanonicalEncodingError, canonical_bytes, canonical_str
from .hashing import DOMAIN_PREFIX, DOMAINS, domain_hash, sha256_hex
from .numbers import NumberError, RawNumber, format_number
from .spans import Span, byte_offset, nfc, placeholder_span, utf8_len

__all__ = [
    "CanonicalEncodingError",
    "canonical_bytes",
    "canonical_str",
    "DOMAIN_PREFIX",
    "DOMAINS",
    "domain_hash",
    "sha256_hex",
    "NumberError",
    "RawNumber",
    "format_number",
    "Span",
    "byte_offset",
    "nfc",
    "placeholder_span",
    "utf8_len",
]
