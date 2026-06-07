"""The ``Source`` protocol — the extensibility seam for transcript adapters.

A source turns its native records into the source-agnostic ``NormalizeResult``. v0.1
implements only ``claude_jsonl``; a future Codex/manual adapter is a new module that
satisfies this protocol, not a rewrite.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..models.event import NormalizeResult

__all__ = ["Source"]


@runtime_checkable
class Source(Protocol):
    name: str

    def read_records(self, text: str) -> list:
        """Parse the raw transcript text into native records (lossless numbers)."""
        ...

    def normalize(self, records: list, *, session_id: str) -> NormalizeResult:
        """Map native records into normalized events + the routing partition."""
        ...
