"""``openproof init`` — create ``.openproof/``, write the ship-by-default ``.gitignore``,
pin ``spec-version``, and record the portable repo fingerprint (§10, §7 step 1, §17 task 1).

Establishes the layout and the Git-safety guarantee (``raw/``/``vault/``/``staging/``
never tracked) BEFORE any import. Binding separates the LOCAL discovery key (never
written) from the COMMITTED portable identity: a fresh/historyless repo records
``{status:"unavailable", reason:"historyless"}`` rather than any path-oracle (§6 item 7).
"""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

from ..canonical import canonical_bytes
from ..config import SPEC_VERSION, Layout
from ..errors import EXIT_OK, UnboundRepoError
from ..git import repo as gitrepo

__all__ = ["run"]


def _gitignore_text() -> str:
    return files("openproof.spec").joinpath("gitignore.tmpl").read_text(encoding="utf-8")


def _identity_summary(identity: dict) -> str:
    if identity.get("status") == "unavailable":
        return "historyless (fresh repo, 0 commits) — committed fingerprint is {status:unavailable}"
    roots = identity.get("rootCommits", [])
    fmt = identity.get("gitObjectFormat", "sha1")
    head = roots[0][:12] if roots else "?"
    return f"available ({fmt}; {len(roots)} root commit(s), first {head}…)"


def run(cwd: Path | str = ".", *, out=print) -> int:
    """Initialize ``.openproof/`` for the repository containing ``cwd``."""
    cwd = Path(cwd)
    if not gitrepo.is_git_repo(cwd):
        raise UnboundRepoError(
            f"{cwd} is not inside a git repository — cannot bind. "
            "Run `git init` (and ideally make ≥1 commit), then `openproof init`."
        )

    repo_root = Path(gitrepo.resolve_toplevel(cwd))
    layout = Layout(repo_root)
    if layout.exists():
        out(f"already initialized: {layout.root} (left untouched)")
        return EXIT_OK

    identity = gitrepo.repository_identity(repo_root)
    layout.root.mkdir(parents=True, exist_ok=True)

    # path → bytes; written via one comprehension (config is canonical JSON + trailing LF).
    artifacts = {
        layout.gitignore: _gitignore_text().encode("utf-8"),
        layout.spec_version: (SPEC_VERSION + "\n").encode("utf-8"),
        layout.config: canonical_bytes({"repoFingerprint": identity}) + b"\n",
    }
    [path.write_bytes(data) for path, data in artifacts.items()]

    out(f"Initialized {layout.root}")
    out(f"  bound repo: {repo_root}")
    out(f"  spec-version: {SPEC_VERSION}")
    out(f"  repository identity: {_identity_summary(identity)}")
    out("  .gitignore: raw/, vault/, staging/ are never tracked (P6).")
    return EXIT_OK
