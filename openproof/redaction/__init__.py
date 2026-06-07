"""The deterministic v0.1 redaction floor (§6.5) — pure, no I/O.

A single frozen pipeline so two conformant redactors produce byte-identical placeholders,
payload, and ids. Public entry point: :func:`redact`.
"""

from __future__ import annotations

from .redactor import redact

__all__ = ["redact"]
