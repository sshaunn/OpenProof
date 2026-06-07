"""The transactional staging → committed promote (§10/§12a/§6 item 6).

Safe-by-default: the candidate receipt is written to the gitignored ``staging/<hash>/``
first; promotion is a signal-masked ``rename → git add → index-verify`` with rollback on
``git add`` failure. The one residual non-atomicity (a crash between rename and index) can
leave an untracked orphan ``committed/<hash>/``, which ``reconcile`` (run on every commit,
reported by status/doctor) detects (F4) and reconciles by the next invocation.
"""

from __future__ import annotations

import os
import shutil
import signal
from pathlib import Path

from ..config import Layout
from ..errors import OpenProofError, ReceiptCorruptionError
from ..git import repo as gitrepo

__all__ = ["RECEIPT_FILES", "write_staging", "promote", "reconcile", "PromoteError"]

RECEIPT_FILES = ("events.jsonl", "unparsed.jsonl", "manifest.yml")


class PromoteError(OpenProofError):
    exit_code = 5


def _rel(layout: Layout, path: Path) -> str:
    return str(path.relative_to(layout.repo_root))


def write_staging(layout: Layout, snapshot) -> Path:
    staging = layout.staging / snapshot.ledger_state_hash
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    (staging / "events.jsonl").write_bytes(snapshot.events_bytes)
    (staging / "unparsed.jsonl").write_bytes(snapshot.unparsed_bytes)
    (staging / "manifest.yml").write_bytes(snapshot.manifest_bytes)
    return staging


def _bytes_match(a: Path, b: Path) -> bool:
    return all((a / f).read_bytes() == (b / f).read_bytes() for f in RECEIPT_FILES)


def _mask_signals() -> dict:
    saved = {}
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            saved[sig] = signal.signal(sig, signal.SIG_IGN)
        except (ValueError, OSError):  # pragma: no cover - not the main thread (worker/test)
            pass
    return saved


def _restore_signals(saved: dict) -> None:
    for sig, handler in saved.items():
        try:
            signal.signal(sig, handler)
        except (ValueError, OSError):  # pragma: no cover - not the main thread
            pass


def promote(layout: Layout, ledger_state_hash: str, *, after_rename_hook=None) -> str:
    """Promote ``staging/<hash>/`` to the tracked ``committed/<hash>/``. Returns
    ``"COMMITTED"`` or ``"DUPLICATE"``. Raises ReceiptCorruptionError (F5) / PromoteError."""
    staging = layout.staging / ledger_state_hash
    committed = layout.committed / ledger_state_hash
    repo_root = layout.repo_root

    if committed.exists():
        if not _bytes_match(staging, committed):
            raise ReceiptCorruptionError(
                f"committed/{ledger_state_hash}/ already exists with NON-identical bytes (F5) — refusing to overwrite an immutable receipt"
            )
        shutil.rmtree(staging)  # idempotent duplicate-commit no-op
        rel = _rel(layout, committed)
        if not gitrepo.tracked_under(repo_root, rel):
            gitrepo.git_add(repo_root, rel)
        return "DUPLICATE"

    committed.parent.mkdir(parents=True, exist_ok=True)
    saved = _mask_signals()
    try:
        os.rename(staging, committed)  # the atomic move into the tracked surface
        if after_rename_hook is not None:
            after_rename_hook()  # failure-injection point (a crash here leaves an orphan)
        rel = _rel(layout, committed)
        if not gitrepo.git_add(repo_root, rel) or not gitrepo.tracked_under(repo_root, rel):
            os.rename(committed, staging)  # rollback on git-add failure
            raise PromoteError("git add failed — rolled back to staging; nothing committed")
        return "COMMITTED"
    finally:
        _restore_signals(saved)


def reconcile(layout: Layout) -> list:
    """Sweep leftover ``staging/`` (uncatchable-termination residue) and reconcile an orphan
    ``committed/<hash>/`` (crash in the rename→index window, F4). Returns human notes."""
    notes = []
    if layout.staging.exists():
        for child in sorted(layout.staging.iterdir()):
            if child.is_dir():
                shutil.rmtree(child)
                notes.append(f"swept leftover staging/{child.name}/")
    if layout.committed.exists():
        for child in sorted(layout.committed.iterdir()):
            rel = _rel(layout, child)
            if child.is_dir() and not gitrepo.tracked_under(layout.repo_root, rel):
                gitrepo.git_add(layout.repo_root, rel)  # re-add the valid orphan receipt
                notes.append(f"reconciled orphan committed/{child.name}/ (re-added to index)")
    return notes
