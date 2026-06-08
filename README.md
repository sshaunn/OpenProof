# OpenProof

[![CI](https://github.com/sshaunn/OpenProof/actions/workflows/ci.yml/badge.svg)](https://github.com/sshaunn/OpenProof/actions/workflows/ci.yml)

A local-first, Git-first **evidence ledger** and **commit-safety gate** around Claude Code.

OpenProof is the tool *around* the AI coding loop, never one of the agents. v0.1 implements
one slice: import Claude Code JSONL → a **redacted, content-addressed, repo-bound evidence
ledger** → promote into Git as an **immutable receipt** you can hand to a second party.

> Status: **v0.1 feature-complete** (package `0.1.1`) — all five commands work end-to-end
> (100% test coverage); `commit --check` adds a gate-only exit-code mode. The published
> on-disk contract is [SPEC.md](SPEC.md) (`spec-version 0.1.0`, frozen); the commercial
> boundary is [COMMERCIAL-BOUNDARY.md](COMMERCIAL-BOUNDARY.md).

## Install

A stdlib-only Python CLI (3.11+). Install globally with [pipx](https://pipx.pypa.io):

```sh
pipx install git+https://github.com/sshaunn/OpenProof.git
pipx ensurepath          # if ~/.local/bin isn't on your PATH yet
openproof --version      # openproof 0.1.1
```

**Upgrade to the latest:**

```sh
pipx upgrade openproof
# if it reports "already at latest" (same version string), force a clean reinstall:
pipx install --force git+https://github.com/sshaunn/OpenProof.git
```

## Quickstart

```sh
cd your-repo
openproof init                     # bind the repo, write the ship-by-default .gitignore
openproof import claude            # capture this repo's Claude sessions (redacted, local, gitignored)
openproof status                   # counts + the release-gate verdict
openproof commit                   # promote a redacted, immutable receipt into Git (human-reviewed)
```

**Capture automatically** — add a Claude Code `SessionEnd` hook (in `~/.claude/settings.json`
for all repos, or `<repo>/.claude/settings.local.json` for one) so every session is recorded
without a manual `import`:

```json
{ "hooks": { "SessionEnd": [ { "hooks": [ { "type": "command",
  "command": "cd \"$CLAUDE_PROJECT_DIR\" && \"$HOME/.local/bin/openproof\" import claude || true" } ] } ] } }
```

(The hook only imports in repos you've `openproof init`'d — elsewhere it's a harmless no-op.)

## Commands (v0.1)

| Command | Purpose |
|---|---|
| `openproof init` | Create `.openproof/`, write the ship-by-default `.gitignore`, pin `spec-version`, bind the repo. |
| `openproof import claude` | Discover + normalize Claude JSONL, redact at the boundary, append to the local ledger. |
| `openproof status` | Binding, counts, unparsed warnings, redaction summary, and the release-gate result. |
| `openproof commit` | The only promotion path: gate → staged receipt → immutable `committed/<ledgerStateHash>/`. `--check` gates without promoting (see below). |
| `openproof doctor` | Read-only diagnostics: re-assert the v0.1 safety invariants. |

## Safety invariant

`raw/`, `vault/`, and `staging/` are **never tracked**. Transcript payload enters Git only as a
deliberate, human-confirmed, redacted receipt under `committed/<ledgerStateHash>/`.

## Gate a dev loop / CI on evidence integrity

`openproof commit --check` runs the full commit-grade release gate and **exits with a clean
code — `0` (PASS) or `5` (blocked) — without staging, prompting, or promoting anything**. A
headless dev→test→review loop calls it directly (no shell wrapper) and halts on a non-zero exit:

```sh
openproof import claude            # capture the latest transcript (or via a SessionEnd hook)
openproof commit --check           # exit 0 = evidence clean → proceed; exit 5 = halt
# add --ack-unparsed to clear N2 (unrecognized record types) non-interactively
```

It guards the **evidence trail** (complete, untampered, no secret in the would-be receipt) —
not your source tree. Promotion into Git stays the deliberate, human-reviewed `openproof commit`.

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
