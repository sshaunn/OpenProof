"""Pinned constants and ``.openproof/`` path layout (§9).

``SPEC_VERSION`` / ``SCHEMA_VERSION`` are frozen v0.1 pins. The spec delegates their
exact literal values to the implementation; they are locked here and asserted by a
golden conformance test, never invented per-run.
"""

from __future__ import annotations

from pathlib import Path

# Frozen v0.1 pins (locked by tests/golden/conformance/test_pins.py).
SPEC_VERSION = "0.1.0"
SCHEMA_VERSION = 1

OPENPROOF_DIRNAME = ".openproof"


class Layout:
    """Resolved ``.openproof/`` paths for a bound repository root."""

    def __init__(self, repo_root: Path):
        self.repo_root = Path(repo_root)
        self.root = self.repo_root / OPENPROOF_DIRNAME

    @property
    def gitignore(self) -> Path:
        return self.root / ".gitignore"

    @property
    def spec_version(self) -> Path:
        return self.root / "spec-version"

    @property
    def config(self) -> Path:
        return self.root / "config.yml"

    # Gitignored, never-tracked payload surfaces (P6/F4).
    @property
    def raw(self) -> Path:
        return self.root / "raw"

    @property
    def vault(self) -> Path:
        return self.root / "vault"

    @property
    def staging(self) -> Path:
        return self.root / "staging"

    # The one tracked transcript surface.
    @property
    def committed(self) -> Path:
        return self.root / "committed"

    @property
    def sessions(self) -> Path:
        return self.root / "sessions"

    @property
    def git_changesets(self) -> Path:
        return self.root / "git" / "changesets.yml"

    def exists(self) -> bool:
        return self.config.exists()
