# OpenProof Build Constitution

> **What this is.** The frozen charter for **how we build OpenProof**. The product design is
> governed by `docs/openproof-v0.1-definition.md` (the WHAT — frozen after 14 review rounds).
> This constitution governs the **process** (the HOW). It adds **nothing** to the product
> scope: it does not create commands, features, or behavior. It is changed only by a
> deliberate, recorded amendment (see §7), exactly like the spec.
>
> **Note on references.** The frozen design spec (`docs/openproof-v0.1-definition.md`), the
> implementation plan, and the build log are the maintainer's **design history** and are kept
> outside this published repository (see `.gitignore`); they are not required to use or build
> the tool. Spec section references like `§12c` point to that history.

---

## 0. NON-NEGOTIABLE — never commit a secret-shaped literal (CON-SEC)

> **INCIDENT (2026-06-07):** GitHub secret scanning flagged **2 secret incidents** on commit
> `31d6486` (build-step-2). The cause: test fixtures contained **contiguous secret-shaped
> literals** — connection-string credentials (`scheme://user:pw@host`) and PEM/JWT blocks —
> and the acceptance gate's B5 check only scanned `openproof/`+`scripts/`, **never `tests/`**.
> A scanner flags the **SHAPE, not the realness**: a fake `redis://admin:…@host` is flagged
> exactly like a real one. **This must NEVER happen again.**

**The iron rule.** **No file committed to this repository may contain a contiguous
secret-shaped token — even a fake/example one.** That includes provider-key prefixes
(`sk-…`, `ghp_…`, `AKIA…`), connection-string credentials, PEM private-key blocks, JWTs,
Bearer tokens, and credential-keyword assignments with a real-looking value. It applies to
**all** tracked files: source, **tests**, fixtures, docs, comments, commit messages.

**How (tests still need secret-shaped INPUTS):** build them at **runtime from inert split
fragments**, never as a contiguous source literal. Use the `fake` fixture
(`tests/conftest.py`): `fake.conn(...)`, `fake.pem(...)`, `fake.provider_key("sk-", n)`,
`fake.jwt(...)`, `fake.bearer(...)`, or split inline (`"sk-" + "A"*30`, `f"KEY={var}"`). The
string is identical at runtime; the *source bytes* never form a scanner-recognizable token.

**Enforced (B5).** The acceptance gate's **B5 scans EVERY git-tracked file** (not just the
package) for these shapes and **FAILS the gate** on any match — so a secret-shaped literal
can never reach a commit. Real secrets (live keys, `.env`) are additionally never tracked
(B4: `vault/`/`raw/`/`staging/` gitignored). When in doubt, construct it; never paste it.

---

## 1. Supreme rule — faithful transcription, invent nothing

Implementation is the **faithful transcription** of the frozen spec into code. **No new
features, no sixth command (the surface is exactly `init`/`import claude`/`status`/`commit`/
`doctor`), no scope additions, no reopening settled decisions, no redesign, no more design
review loops.** Where the spec delegates a pure implementation detail, pick the **simplest
spec-faithful option and lock it with a golden test** — that is pinning, not inventing. When
genuinely blocked or the spec looks wrong, **stop and ask the founder** — do not freelance.
(Full rule: the `implementation-discipline-no-new-ideas` memory.)

The acceptance gate **mechanically enforces** the frozen 5-command surface (B6), so this
rule cannot silently drift.

## 2. The build loop — dev → test → review, one step at a time

We build in the spec's `§5` order, one step at a time. **Every step runs the full loop:**

1. **Dev** — write the smallest spec-faithful slice of code (functional-first, §6).
2. **Test** — write its tests across all required layers (§3) to **full coverage** *before the
   step is considered done*. Tests are written to the spec, not to the code.
3. **Review** — run the **acceptance gate** (§4). The founder reviews the **tests** (the
   review surface, §3), not every line. A step is **"done" only on an aggregate gate PASS**,
   recorded in the build log (`docs/openproof-build-log.md`).

No step is promoted (called done / eligible to commit) while the gate is red.

## 3. Testing standard — the review surface

**The founder reviews testing, not every code block. Therefore the tests must be exhaustive,
readable, and tell the story of what is guaranteed.** Four layers are **required**, and the
gate checks the first three are present and the suite is green:

| Layer | `tests/…` | What it proves |
|---|---|---|
| **Unit** | `unit/` | one pure function/class in isolation, no I/O |
| **Component** | `component/` | one module/subsystem through its public interface, in a sandboxed fs/git |
| **Scenario** | `scenario/` | an **end-to-end user story** from the spec (`§7` workflow / `§17` tasks), written as **given/when/then**, asserting user-observable outcomes **and** safety invariants — not just "the function returned" |
| **Golden / conformance** | `golden/conformance/` | frozen cross-implementation **byte/hash vectors** (`§12c` / `§17` task 10); the determinism lock a future port must reproduce |

**Coverage bar: 100% line coverage** of the `openproof/` package, enforced by the gate.
`# pragma: no cover` is permitted **only** for genuinely defensive/unreachable branches, each
with a one-line justification. (Branch coverage is a future tightening.)

Scenario tests are the load-bearing layer the founder asked for: every spec scenario
(`§17` task 10 — normal, drift, secret, unpaired-tool, re-import idempotence, the
cross-implementation conformance set, …) becomes an executable scenario as its feature is
built. Integration tests alone do **not** satisfy this.

## 4. The acceptance gate — deterministic, dogfood of §12

`python scripts/acceptance_gate.py` is the build gate. It is the **dogfood** of the product's
own release gate: a registry of deterministic predicates, aggregate **PASS** only if all pass,
non-zero exit otherwise (wires into pre-commit / CI). It is **not** a product command.

| Predicate | Asserts |
|---|---|
| **B1 tests green** | the whole suite passes |
| **B2 coverage 100%** | line coverage of `openproof/` is 100% |
| **B3 test layers present** | `unit/` + `component/` + `scenario/` all exist and are non-empty |
| **B4 payload never tracked (P6)** | `git ls-files .openproof/raw .openproof/vault .openproof/staging` is empty |
| **B5 no secret in tool source** | no §6.5 tier-A secret literal in `openproof/` or `scripts/` |
| **B6 frozen 5-command surface** | the CLI exposes exactly `init`/`import(claude)`/`status`/`commit`/`doctor` |

A step is done **only** when the gate aggregates PASS.

## 5. Dogfood — build the tool with the tool's own mind

We build **as if OpenProof's gate were already watching** (`§6a` of the plan):

- **Safety invariants always hold**: `raw/`, `vault/`, `staging/` are never tracked (B4); the
  only tracked transcript surface is a deliberate `committed/<ledgerStateHash>/` receipt.
- **Secrets never leave the floor**: no secret literal in tool source (B5); real example
  secrets live only in test fixtures, never in shipped code.
- **Evidence over assertion**: each build step appends a **receipt** to
  `docs/openproof-build-log.md` — what was built, the evidence, and the gate verdict. This is
  the manual analog of the OpenProof ledger until `import`/`commit` can produce the real one
  (build steps 4 & 6), at which point this repo's own history becomes the first real ledger.
- **No hand-faked tool output**: `config.yml` / `spec-version` / receipt bytes are produced by
  the tool, never hand-written (only the bootstrap `.gitignore` was).

## 6. Coding style — functional-first

Higher-order functions, comprehensions, registries/data-driven dispatch, and composition of
small pure functions are the default; plain imperative blocks only for genuinely trivial
branches; no Java-style one-class-per-Predicate boilerplate. Data lives in frozen dataclasses;
behavior lives in pure functions over them. (Full rule: plan `§2.1` + the
`coding-style-functional-first` memory.)

## 7. Amendment

This constitution is frozen like the spec. A change is a deliberate, founder-approved
amendment recorded here with a date and reason. It may tighten the process (e.g. add branch
coverage, a new gate predicate) but may **never** relax the supreme rule (§1) or the safety
invariants (§5).

| # | Date | Amendment |
|---|---|---|
| 1 | 2026-06-07 | Ratified at build-step-1: the four test layers, 100% line coverage, the six-predicate acceptance gate, and the dogfood receipt trail. |
| 2 | 2026-06-07 | **§0 CON-SEC added after a real GitHub secret-scanning incident** on `31d6486` (secret-shaped literals in test fixtures): no committed secret-shaped literal anywhere; test fixtures build them at runtime via the `fake` fixture; **B5 now scans every git-tracked file**, and the offending history was purged. |
