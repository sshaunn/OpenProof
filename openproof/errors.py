"""Typed errors + documented exit codes (plan §2 principle 7).

The CLI maps these to process exit codes so later pre-commit/CI use is well-defined.
The release-gate verdicts (fast-follow wiring) reuse the same code space:
0 = success/PASS, non-zero = a specific failure class.
"""

from __future__ import annotations

# Exit codes.
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_UNBOUND = 3  # N1 — cwd null / non-git / fingerprint mismatch
EXIT_NOT_INITIALIZED = 4


class OpenProofError(Exception):
    """Base for all expected, message-carrying failures. Maps to ``exit_code``."""

    exit_code = EXIT_ERROR


class UnboundRepoError(OpenProofError):
    """N1 — the working directory does not resolve to a bindable git repository."""

    exit_code = EXIT_UNBOUND


class NotInitializedError(OpenProofError):
    """``.openproof/`` is absent; ``openproof init`` has not been run here."""

    exit_code = EXIT_NOT_INITIALIZED
