"""The §12a frozen ``sourceBoundary`` capture (LOCAL-ONLY).

Claude session files are live append logs, so import first captures, per file, a frozen
prefix over ``[0, byteLengthAtOpen)`` — reading NOTHING past it. An incomplete final line
(a partial append in flight) is IGNORED, never counted. ``sourcePrefixDigestLocalOnly``
is a content commitment to those exact bytes; it is LOCAL-ONLY (a digest of unredacted
source bytes) and detects an in-place rewrite that preserves length/count (P4).
"""

from __future__ import annotations

import hashlib
import json

from ..canonical.hashing import domain_hash
from ..models.session import SourceBoundary

__all__ = ["frozen_prefix", "prefix_digest", "capture_boundary", "P4_SAME", "P4_GROWN", "P4_REWRITTEN"]

P4_SAME, P4_GROWN, P4_REWRITTEN = "SAME", "GROWN", "REWRITTEN"


def frozen_prefix(data: bytes) -> bytes:
    """The bytes up to and including the last complete line; a partial trailing line is dropped."""
    last_lf = data.rfind(b"\n")
    return data[: last_lf + 1] if last_lf != -1 else b""


def prefix_digest(prefix: bytes) -> str:
    """A LOCAL-ONLY content commitment to the exact prefix bytes (never committed)."""
    return domain_hash("source-prefix-local", {"prefixSha256": hashlib.sha256(prefix).hexdigest()})


def _last_native_anchor(prefix: bytes) -> str:
    """The nativeAnchor (uuid|tool_use_id) of the last complete record — LOCAL-ONLY."""
    lines = [line for line in prefix.split(b"\n") if line.strip()]
    if not lines:
        return ""
    try:
        return json.loads(lines[-1]).get("uuid") or ""
    except (json.JSONDecodeError, AttributeError):
        return ""


def capture_boundary(source: str, session_id: str, data: bytes, *, file_identity: str) -> SourceBoundary:
    prefix = frozen_prefix(data)
    count = sum(1 for line in prefix.split(b"\n") if line.strip())
    return SourceBoundary(
        source=source,
        session_id=session_id,
        file_identity_local=file_identity,
        byte_length_at_open=len(prefix),
        complete_record_count_at_open=count,
        last_complete_record_index=count - 1,
        last_complete_native_anchor=_last_native_anchor(prefix),
        source_prefix_digest_local=prefix_digest(prefix),
    )


def compare_boundary(prior: SourceBoundary, data: bytes) -> str:
    """Classify a re-read against the recorded boundary (P4): SAME / GROWN / REWRITTEN."""
    recomputed_prior = prefix_digest(frozen_prefix(data[: prior.byte_length_at_open]))
    if recomputed_prior != prior.source_prefix_digest_local:
        return P4_REWRITTEN
    return P4_GROWN if len(frozen_prefix(data)) > prior.byte_length_at_open else P4_SAME
