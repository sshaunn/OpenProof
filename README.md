# OpenProof

[![CI](https://github.com/sshaunn/OpenProof/actions/workflows/ci.yml/badge.svg)](https://github.com/sshaunn/OpenProof/actions/workflows/ci.yml)

A local-first, Git-first **evidence ledger** and **commit-safety gate** around Claude Code.

OpenProof is the tool *around* the AI coding loop, never one of the agents. v0.1 implements
one slice: import Claude Code JSONL → a **redacted, content-addressed, repo-bound evidence
ledger** → promote into Git as an **immutable receipt** you can hand to a second party.

> Status: **v0.1 feature-complete** — all five commands work end-to-end (100% test coverage).
> The published on-disk contract is [SPEC.md](SPEC.md); the commercial boundary is
> [COMMERCIAL-BOUNDARY.md](COMMERCIAL-BOUNDARY.md).

## Commands (v0.1)

| Command | Purpose |
|---|---|
| `openproof init` | Create `.openproof/`, write the ship-by-default `.gitignore`, pin `spec-version`, bind the repo. |
| `openproof import claude` | Discover + normalize Claude JSONL, redact at the boundary, append to the local ledger. |
| `openproof status` | Binding, counts, unparsed warnings, redaction summary, and the release-gate result. |
| `openproof commit` | The only promotion path: gate → staged receipt → immutable `committed/<ledgerStateHash>/`. |
| `openproof doctor` | Read-only diagnostics: re-assert the v0.1 safety invariants. |

## Safety invariant

`raw/`, `vault/`, and `staging/` are **never tracked**. Transcript payload enters Git only as a
deliberate, human-confirmed, redacted receipt under `committed/<ledgerStateHash>/`.

## Develop

Building OpenProof follows a frozen process charter — see [CONSTITUTION.md](CONSTITUTION.md):
**dev → test → review**, where tests are the review surface (unit · component · scenario ·
golden), 100% line coverage, and every build step must pass the acceptance gate.

```sh
make install   # editable install + dev tools
make test      # full suite: tests/{unit,component,scenario,golden}
make cov       # tests with the 100% line-coverage gate
make gate      # the build acceptance gate (dogfood of §12): B1–B6
make loop      # cov + gate — the per-step review
python -m openproof --help
```

Requires Python 3.11+. v0.1 has zero runtime dependencies (stdlib-only).

## License

Apache-2.0.
