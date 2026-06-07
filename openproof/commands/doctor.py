"""``openproof doctor`` — read-only diagnostics; writes nothing, no network (§10, §17 task 7).

Re-asserts the v0.1 safety invariants on demand: the §12a P6 ``git ls-files`` tracked-path
check, the gitignore exclusions, config/spec-version presence, and orphan
``committed/<hash>/`` detection (the F4 condition). Never prints an unqualified "safe".
"""

from __future__ import annotations

from pathlib import Path

from ..config import Layout
from ..errors import EXIT_ERROR, EXIT_OK, NotInitializedError, UnboundRepoError
from ..gate.predicates import NEVER_TRACKED
from ..git import repo as gitrepo

__all__ = ["run", "diagnostics"]


def diagnostics(layout: Layout) -> list:
    """Return ``(name, ok, detail)`` invariant checks (pure-ish: reads files + git index)."""
    repo_root = layout.repo_root
    checks = []

    tracked = gitrepo.tracked_under(repo_root, *NEVER_TRACKED)
    checks.append(("P6 raw/ vault/ staging/ never tracked", not tracked,
                   "zero tracked paths" if not tracked else f"TRACKED: {tracked}"))

    gitignore = layout.gitignore.read_text(encoding="utf-8") if layout.gitignore.exists() else ""
    excludes = all(token in gitignore for token in ("vault/", "raw/", "staging/"))
    checks.append((".gitignore excludes vault/ raw/ staging/", excludes,
                   "present" if excludes else "missing exclusions"))

    present = layout.config.exists() and layout.spec_version.exists()
    checks.append(("config.yml + spec-version present", present, "present" if present else "missing"))

    # F4: an orphan committed/<hash>/ in the working tree but absent from the Git index
    orphans = []
    if layout.committed.exists():
        for child in sorted(layout.committed.iterdir()):
            rel = str(child.relative_to(repo_root))
            if child.is_dir() and not gitrepo.tracked_under(repo_root, rel):
                orphans.append(rel)
    checks.append(("no orphan committed/<hash>/ (F4)", not orphans,
                   "none" if not orphans else f"untracked orphan(s): {orphans}"))
    return checks


def run(cwd: Path | str = ".", *, out=print) -> int:
    cwd = Path(cwd)
    if not gitrepo.is_git_repo(cwd):
        raise UnboundRepoError(f"{cwd} is not inside a git repository — cannot bind.")
    repo_root = Path(gitrepo.resolve_toplevel(cwd))
    layout = Layout(repo_root)
    if not layout.exists():
        raise NotInitializedError("`.openproof/` not found — run `openproof init` first.")

    checks = diagnostics(layout)
    out("openproof doctor — read-only diagnostics")
    for name, ok, detail in checks:
        out(f"  [{'PASS' if ok else 'FAIL'}] {name} — {detail}")
    healthy = all(ok for _, ok, _ in checks)
    out("  All v0.1 safety invariants hold." if healthy else "  INVARIANT VIOLATION — see above.")
    return EXIT_OK if healthy else EXIT_ERROR
