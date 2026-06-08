# OpenProof — Commercial Boundary

> What is always free and open vs. what may later be offered commercially. This file is the
> honest contract; it exists from v0.1 so the boundary is never retroactively moved.

## Always free & open (Apache-2.0) — forever

The **entire v0.1 tool** and its on-disk contract are open and free, with **no paid code**:

- All five CLI commands: `init`, `import claude`, `status`, `commit`, `doctor`.
- The local evidence ledger: normalization, the redaction safety floor, content-addressing,
  the canonical encoding, the `vault/`, and the append-only `raw/` layer.
- The release acceptance gate (P1–P6 / F1–F5 / N1–N3) and `ledgerStateHash`.
- The committed receipt format (`events.jsonl` / `unparsed.jsonl` / `manifest.yml`) and the
  published `.openproof/` spec (`SPEC.md`) — so any second party can verify a receipt with
  open tools, forever, with no lock-in.
- The fast-follow open layers (memory/task/pack/report) once they ship.

**Local-only and private by default.** v0.1 runs entirely on your machine; nothing is sent
anywhere. The default state cannot leak (`raw/`/`vault/`/`staging/` are never tracked).

## Reserved for a possible future commercial offering

No such product exists in v0.1, and none is required to use OpenProof. A future **hosted**
offering, if built, would be limited to genuinely multi-party / network services that a
local CLI cannot provide — for example neutral cross-agent **attestation/notarization** of a
content-hashed gate verdict, or conflict-resolved **team-memory sync**. The decision between
these is open (design doc item C17).

**Boundary guarantees:**
- The local tool, the receipt format, and the spec never move behind a paywall.
- A commercial layer, if it exists, operates **only** on the already-redacted, content-hashed
  artifacts the open tool produces — it never requires handing over unredacted secrets.
- No telemetry, no network calls, and no "phone-home" are added to the open CLI.
