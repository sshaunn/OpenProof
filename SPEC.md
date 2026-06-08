# OpenProof v0.1 — the `.openproof/` specification

> The published, versioned on-disk contract for an OpenProof evidence ledger. A second
> party can verify a committed receipt from this document alone. `spec-version: 0.1.0`,
> RawEvent `schemaVersion: 1`. Apache-2.0.

OpenProof is a local-first, Git-first **evidence ledger** + **commit-safety gate** around
Claude Code. It imports Claude session JSONL into a redacted, content-addressed, repo-bound
ledger, and promotes a gate-passing snapshot into Git as an immutable receipt.

## 1. Commands (the complete v0.1 surface — exactly five)

| Command | Effect |
|---|---|
| `openproof init` | Create `.openproof/`, write the ship-by-default `.gitignore`, pin `spec-version`, record the portable repo fingerprint. |
| `openproof import claude` | Discover this repo's Claude JSONL, normalize, redact at the boundary, append the redacted projection to local `raw/` and originals to `vault/`. |
| `openproof status` | Binding, per-session counts, unparsed warnings, redaction summary, the release-gate result, and the qualified disclosure. |
| `openproof commit` | The only Git-promotion path: re-run the gate (abort unless PASS), build the immutable content-addressed receipt, and promote it transactionally. `--check` evaluates the same gate and exits `0` (PASS) / `5` (blocked) **without** staging, prompting, or promoting — a dev-loop / CI gate. `--ack-unparsed` clears N2 first. |
| `openproof doctor` | Read-only diagnostics: re-assert the safety invariants. |

## 2. On-disk layout

```
.openproof/
  spec-version            # pinned spec version (tracked)
  config.yml              # repoFingerprint (canonical JSON; tracked; no path-oracle)
  .gitignore              # excludes vault/ raw/ staging/ + index cache (ships at init)
  raw/                    # LOCAL, GITIGNORED, NEVER TRACKED — redacted append-only events
    <source>/<sessionId>.jsonl
    _unparsed/<source>/<sessionId>.jsonl     # surfaced unknown records (never dropped)
    _boundaries/<source>-<sessionId>.json    # LOCAL-ONLY frozen sourceBoundary (P4)
  vault/                  # LOCAL-ONLY, GITIGNORED — originals; never a citation target
    secrets-map.json                          # placeholderId -> original (reversible)
    raw-unredacted/<source>/<sessionId>.jsonl # unredacted mirror
  staging/<ledgerStateHash>/   # GITIGNORED, NEVER TRACKED — the commit candidate
  committed/<ledgerStateHash>/ # TRACKED immutable receipt — the ONE tracked transcript surface
    events.jsonl  unparsed.jsonl  manifest.yml
  sessions/<source>-<sessionId>.yml  # ImportedSession summary (tracked)
```

**Safety invariant (P6/F4):** `raw/`, `vault/`, `staging/` are NEVER tracked — asserted by
`git ls-files .openproof/raw .openproof/vault .openproof/staging` being empty. Transcript
content enters Git only as a deliberate, gate-passing `committed/<ledgerStateHash>/` receipt.

## 3. Event model

`kind ∈ {prompt, assistant_msg, tool_call, tool_result, meta}`. An `assistant` record's text
blocks aggregate into one `assistant_msg`; each `tool_use` → one `tool_call` (keyed by its
id); each `thinking` block → one `assistant_msg` carrying a self-describing omission payload
(the thinking text and signature are never serialized). A `user` record → a `prompt` or
`tool_result` event(s) paired by `tool_use_id`. Unknown record types route to `_unparsed/`.

The content-addressed **RawEvent id** = `SHA-256(canonical({domain:"openproof/v1/rawevent-id",
source, sessionId, nativeAnchor, payload, schemaVersion}))` — `seq` excluded — so re-import is
idempotent and byte-identical-content records dedupe (with merged `rawOffsets[]`).

## 4. Redaction floor (the safety floor)

A single deterministic pipeline redacts tier-A secrets at the import boundary, replacing each
matched span with a disclosed `<REDACTED:type#n>` placeholder. Families (by precedence):
private-key blocks, provider-key prefixes, bearer tokens, connection-string credentials,
JWTs, and credential-keyword assignments (the whole trailing `_`/`.`-segment rule). A
marker is `{placeholderId, type, fieldPath, span}`; `placeholderId` derives from redacted
**location only** (never the secret value), so two sources differing only in a secret value
produce byte-identical placeholders (the no-oracle property). Originals live only in
`vault/secrets-map.json`. **Disclosure is qualified — the word "safe" is never unqualified.**

## 5. Canonical encoding (the determinism contract)

One frozen encoding governs every hash input AND every committed byte: UTF-8 + NFC
(NFC sibling-key collision fails closed); object keys sorted by Unicode code point at every
level; non-ASCII as raw UTF-8 (no `\u`); a lossless numeric domain (exact arbitrary-precision
integers, binary64 shortest-positional non-integers with over-precision rejected, `-0`→`0`,
non-finite rejected); LF separators, exactly one trailing LF per file. Every SHA-256 is
`SHA-256(canonical({domain, ...fields}))` with a distinct `openproof/v1/<kind>` domain tag.

## 6. Release acceptance gate (`status` / `commit` / `doctor`)

Deterministic over the on-disk ledger. **PASS** requires P1 binding resolved · P2 no record
silently dropped (the per-session set-partition) · P3 pairing complete · P4 idempotent
re-import · P5 redaction applied + reversible · P6 transcript payload never tracked.
**FAIL (F1–F5)** on a partition violation, an interior unpaired `tool_use`, a re-import id
change, **any matched secret literal surviving** in `raw/` or a receipt, or a same-hash
receipt written with non-identical bytes. **NEEDS_HUMAN_REVIEW (N1–N3)** on an unbound
session, unacknowledged unparsed types, or low-confidence git attribution.

## 7. The committed receipt + `ledgerStateHash`

`ledgerStateHash = SHA-256(canonical({domain:"openproof/v1/ledger-state", ...INCLUDE}))` over
exactly: schemaVersion, spec-version, repoFingerprint, mode, the committed event ids each
paired with `eventRecordHash`, the ImportedSession summaries, the GitChangeSet refs +
`evidenceBoundary`, redactionSummary, the gate predicate results, and the unparsed
opaque-record triples. **Every committed byte is a pure function of this INCLUDE set** —
no wall-clock/person/absolute-path field is ever written into a receipt. The promote is
transactional (signal-masked rename → `git add` → index-verify → rollback); a duplicate
commit is an idempotent no-op; a non-identical same-hash receipt hard-aborts (F5).

## 8. Versioning & fast-follow

`spec-version` pins the full three-layer schema; RawEvent `schemaVersion` pins the raw-event
contract (frozen). **Fast-follow (spec'd, not in v0.1):** `memory/`, `tasks/`, `packs/`,
`reports/` entities and the `review`/`task`/`pack`/`gate`/`export` commands — documented so
the on-disk contract is stable, but written by no v0.1 command.
