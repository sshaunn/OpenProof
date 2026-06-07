"""``openproof commit`` — the only promotion path into Git (§10, §17 task 8).

Reconcile → load the ledger → build the deterministic receipt → re-run the release gate
(abort unless PASS) → write the candidate to gitignored ``staging/<hash>/`` → print the
disclosure + external-scan instruction → confirm → promote transactionally.
"""

from __future__ import annotations

import json
import datetime
from pathlib import Path

from ..canonical.encoding import canonical_bytes
from ..config import SCHEMA_VERSION, SPEC_VERSION, Layout
from ..errors import EXIT_OK, GateBlockedError, NotInitializedError, UnboundRepoError
from ..gate import DISCLOSURE, evaluate_commit
from ..gate.predicates import GIT_ONLY_DISCLOSURE, PASS, compaction_ceiling, read_sessions
from ..git import repo as gitrepo
from ..commit.promote import promote, reconcile, write_staging
from ..commit.snapshot import CLAUDE_LEDGER, GIT_ONLY_EVIDENCE, build_snapshot
from ..ledger.store import iter_sessions, read_unparsed

__all__ = ["run"]


def _read_raw_events(layout: Layout, source: str, session_id: str) -> list:
    # the raw/ lines are ALREADY canonical, so plain json round-trips byte-identically
    # (Python int is arbitrary-precision; floats re-emit their shortest round-trip).
    path = layout.raw / source / f"{session_id}.jsonl"
    if not path.exists():  # pragma: no cover - defensive: write_session always writes raw/
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _git_facts(layout: Layout) -> dict:
    repo_root = layout.repo_root
    head = gitrepo._git(["rev-parse", "HEAD"], repo_root)
    branch = gitrepo._git(["rev-parse", "--abbrev-ref", "HEAD"], repo_root)
    status = gitrepo._git(["-c", "core.quotePath=false", "status", "--porcelain"], repo_root)
    files = sorted(line[3:] for line in status.stdout.splitlines() if line[3:].strip())
    return {
        "headSha": head.stdout.strip() if head.returncode == 0 else None,
        "branch": branch.stdout.strip() if branch.returncode == 0 else None,
        "workingTreeFiles": files,
    }


def _ack_unparsed(layout: Layout) -> None:
    """Persist the N2 acknowledgment into each session's yml: the hash-bound
    unparsedAcknowledgedTypes plus the WHO/WHEN audit fields (unparsedAcknowledgedBy/At) —
    which are §12c EXCLUDE fields, local audit only, NEVER written into the receipt."""
    who = gitrepo._git(["config", "user.name"], layout.repo_root).stdout.strip() or "local"
    when = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    for path in sorted(layout.sessions.glob("*.yml")):
        summary = json.loads(path.read_text(encoding="utf-8"))
        if summary.get("unparsedRecordCount", 0) > 0:
            summary["unparsedAcknowledgedTypes"] = sorted(summary.get("unparsedTypes", []))
            summary["unparsedAcknowledgedBy"] = who
            summary["unparsedAcknowledgedAt"] = when
            path.write_bytes(canonical_bytes(summary) + b"\n")


def run(cwd: Path | str = ".", *, out=print, confirm=None, ack_unparsed=False, after_rename_hook=None) -> int:
    cwd = Path(cwd)
    if not gitrepo.is_git_repo(cwd):
        raise UnboundRepoError(f"{cwd} is not inside a git repository — cannot bind.")
    repo_root = Path(gitrepo.resolve_toplevel(cwd))
    layout = Layout(repo_root)
    if not layout.exists():
        raise NotInitializedError("`.openproof/` not found — run `openproof init` first.")

    for note in reconcile(layout):  # sweep stale staging + reconcile any orphan committed/ (F4)
        out(f"  reconcile: {note}")
    if ack_unparsed:
        _ack_unparsed(layout)

    # load the ledger state
    sessions = read_sessions(layout)
    repo_fingerprint = json.loads(layout.config.read_bytes())["repoFingerprint"]
    mode = CLAUDE_LEDGER if sessions else GIT_ONLY_EVIDENCE
    event_lines, unparsed_by_session, redaction_summary = [], {}, {}
    for source, session_id in iter_sessions(layout):
        event_lines.extend(_read_raw_events(layout, source, session_id))
        records = read_unparsed(layout, source, session_id)
        if records:
            unparsed_by_session[(source, session_id)] = records
    for summary in sessions:
        for kind, count in summary.get("redactionSummary", {}).items():
            redaction_summary[kind] = redaction_summary.get(kind, 0) + count

    snapshot = build_snapshot(
        schema_version=SCHEMA_VERSION, spec_version=SPEC_VERSION, repo_fingerprint=repo_fingerprint,
        mode=mode, event_lines=event_lines, sessions=sessions, unparsed_by_session=unparsed_by_session,
        git_changesets=[], git_facts=_git_facts(layout) if mode == GIT_ONLY_EVIDENCE else {},
        redaction_summary=redaction_summary, gate_results=[],
    )
    # the gate's recorded results are themselves an INCLUDE input (item 9) — rebuild with them
    secrets_map = json.loads((layout.vault / "secrets-map.json").read_text(encoding="utf-8")) \
        if (layout.vault / "secrets-map.json").exists() else {}
    vault_originals = [v["original"] for v in secrets_map.values()] + [e.original for e in snapshot.vault_entries]
    unparsed_envelopes = [
        json.loads(line) for line in snapshot.unparsed_bytes.decode("utf-8").splitlines() if line.strip()
    ]
    # F4 scans the transcript payloads (events + unparsed) — these are independent of the
    # gate results (an INCLUDE input, item 9), so there is no circularity with the manifest.
    verdict = evaluate_commit(
        layout, event_lines=event_lines, sessions=sessions, unparsed_envelopes=unparsed_envelopes,
        vault_originals=vault_originals, receipt_bytes=snapshot.events_bytes + snapshot.unparsed_bytes,
    )

    out("Release gate:")
    for name, result, detail in verdict.results:
        out(f"  [{result}] {name} — {detail}")
    if verdict.aggregate != PASS:
        raise GateBlockedError(f"release gate is {verdict.aggregate}; commit aborted (no promotion)")

    # rebuild the receipt WITH the gate results (item 9) so the manifest is self-describing
    snapshot = build_snapshot(
        schema_version=SCHEMA_VERSION, spec_version=SPEC_VERSION, repo_fingerprint=repo_fingerprint,
        mode=mode, event_lines=event_lines, sessions=sessions, unparsed_by_session=unparsed_by_session,
        git_changesets=[], git_facts=_git_facts(layout) if mode == GIT_ONLY_EVIDENCE else {},
        redaction_summary=redaction_summary, gate_results=[list(r) for r in verdict.results],
    )

    staging = write_staging(layout, snapshot)
    out(f"  {DISCLOSURE}")
    if mode == GIT_ONLY_EVIDENCE:
        out(f"  {GIT_ONLY_DISCLOSURE}")
    compactions = sum(s.get("compactionBoundaryCount", 0) for s in sessions)
    if compactions:
        out(f"  {compaction_ceiling(compactions)}")
    out(f"Candidate ready at {staging} — run any external scanner in another terminal, then confirm.")
    out(f"Will add: .openproof/committed/{snapshot.ledger_state_hash}/ (events.jsonl, unparsed.jsonl, manifest.yml)")

    if confirm is None:  # pragma: no cover - interactive default (tests inject confirm)
        confirm = lambda: input("Promote into Git? [y/N] ").strip().lower() == "y"
    # a catchable termination while waiting at the prompt (SIGINT/EOF) removes the staged
    # candidate; nothing is committed (uncatchable termination is swept by the next reconcile)
    try:
        approved = confirm()
    except (KeyboardInterrupt, EOFError):
        reconcile(layout)
        out("Interrupted — staging removed; nothing committed.")
        return EXIT_OK
    if not approved:
        reconcile(layout)  # remove the staged candidate; nothing committed
        out("Declined — staging removed; nothing committed.")
        return EXIT_OK

    result = promote(layout, snapshot.ledger_state_hash, after_rename_hook=after_rename_hook)
    out(f"{result}: committed/{snapshot.ledger_state_hash}/ ({'already present, idempotent' if result == 'DUPLICATE' else 'staged into Git index'})")
    return EXIT_OK
