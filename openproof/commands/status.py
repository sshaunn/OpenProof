"""``openproof status`` — binding, counts, unparsed warnings, redaction summary, and the
§12a release-gate result, ending with the qualified disclosure (§10, §17 task 7)."""

from __future__ import annotations

from pathlib import Path

from ..config import Layout
from ..errors import EXIT_OK, NotInitializedError, UnboundRepoError
from ..gate import DISCLOSURE, evaluate
from ..gate.predicates import GIT_ONLY_DISCLOSURE, compaction_ceiling, read_sessions
from ..git import repo as gitrepo

__all__ = ["run"]


def run(cwd: Path | str = ".", *, out=print) -> int:
    cwd = Path(cwd)
    if not gitrepo.is_git_repo(cwd):
        raise UnboundRepoError(f"{cwd} is not inside a git repository — cannot bind.")
    repo_root = Path(gitrepo.resolve_toplevel(cwd))
    layout = Layout(repo_root)
    if not layout.exists():
        raise NotInitializedError("`.openproof/` not found — run `openproof init` first.")

    sessions = read_sessions(layout)
    out(f"OpenProof status — {repo_root}")
    out(f"  spec-version: {layout.spec_version.read_text(encoding='utf-8').strip()}")
    out(f"  mode: {'CLAUDE_LEDGER' if sessions else 'GIT_ONLY_EVIDENCE (no transcript imported)'}")
    for s in sessions:
        out(f"  session {s['sessionId']}: {s['eventCount']} events / {s['sourceRecordCount']} records — "
            f"{s['unparsedRecordCount']} unparsed, {sum(s.get('redactionSummary', {}).values())} redactions"
            + (f", {s['compactionBoundaryCount']} compaction-boundary" if s.get('compactionBoundaryCount') else ""))

    verdict = evaluate(layout)
    out("  release gate:")
    for name, result, detail in verdict.results:
        out(f"    [{result}] {name} — {detail}")
    out(f"  AGGREGATE: {verdict.aggregate}")
    if not sessions:
        out(f"  {GIT_ONLY_DISCLOSURE}")
    compactions = sum(s.get("compactionBoundaryCount", 0) for s in sessions)
    if compactions:  # §12a binding compaction-ceiling disclosure
        out(f"  {compaction_ceiling(compactions)}")
    out(f"  {DISCLOSURE}")
    return EXIT_OK
