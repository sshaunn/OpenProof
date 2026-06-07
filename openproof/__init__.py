"""OpenProof — a local-first, Git-first evidence ledger and commit-safety gate around
Claude Code. v0.1 implements one slice: import Claude JSONL → a redacted,
content-addressed, repo-bound evidence ledger → promote to Git as an immutable receipt.

See ``docs/openproof-v0.1-definition.md`` (the frozen spec) and
``docs/openproof-implementation-plan.md`` (the build plan).
"""

from __future__ import annotations

__version__ = "0.1.0"
