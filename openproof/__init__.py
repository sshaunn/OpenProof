"""OpenProof — a local-first, Git-first evidence ledger and commit-safety gate around
Claude Code. v0.1 implements one slice: import Claude JSONL → a redacted,
content-addressed, repo-bound evidence ledger → promote to Git as an immutable receipt.

See ``docs/openproof-v0.1-definition.md`` (the frozen spec) and
``docs/openproof-implementation-plan.md`` (the build plan).
"""

from __future__ import annotations

# package version (independent of the FROZEN on-disk `SPEC_VERSION`/`SCHEMA_VERSION`).
# 0.1.1 adds `commit --check` (gate-only exit code); the spec contract is unchanged.
__version__ = "0.1.1"
