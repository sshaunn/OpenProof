"""Build the deterministic committed receipt + ``ledgerStateHash`` (§12c).

Every committed byte is a pure function of the §12c INCLUDE set under the one frozen
canonical encoding, so two runs over the same ledger produce byte-identical
``events.jsonl`` / ``unparsed.jsonl`` / ``manifest.yml`` (the receipt-byte invariant).
No EXCLUDE field (wall-clock/person/absolute-path) is ever written here.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..canonical.encoding import canonical_bytes
from ..canonical.hashing import domain_hash
from ..canonical.timestamps import normalize_ts
from ..models.redaction import VaultEntry
from ..redaction import redact

__all__ = ["Snapshot", "event_record_hash", "build_unparsed_envelope", "build_snapshot",
           "CLAUDE_LEDGER", "GIT_ONLY_EVIDENCE"]

CLAUDE_LEDGER, GIT_ONLY_EVIDENCE = "CLAUDE_LEDGER", "GIT_ONLY_EVIDENCE"

# local fields stripped from an unparsed record before it is redacted into the receipt:
# `cwd` is an absolute path (never committed); the rest are carried as core fields.
_UNPARSED_STRIP = {"cwd", "type", "subtype", "sessionId"}


@dataclass(frozen=True)
class Snapshot:
    ledger_state_hash: str
    events_bytes: bytes
    unparsed_bytes: bytes
    manifest_bytes: bytes
    vault_entries: tuple


def event_record_hash(event_line: dict) -> str:
    """§12c item-5 ``eventRecordHash`` over the REDACTED committed event core."""
    return domain_hash("event-record", {"core": event_line})


def _jsonl(dicts) -> bytes:
    return b"".join(canonical_bytes(d) + b"\n" for d in dicts)


def build_unparsed_envelope(unparsed: dict, source: str, session_id: str, schema_version: int):
    """Return ``(committed_envelope, (opaqueId, redactedRecordHash, redactedPayloadHash), vault)``
    for one unknown record (§12c item 10 / §9 unparsed.jsonl)."""
    payload_in = {k: v for k, v in unparsed["raw"].items() if k not in _UNPARSED_STRIP}
    redaction = redact(payload_in, source=source, session_id=session_id, record_index=unparsed["recordIndex"])

    core = {
        "source": source,
        "sessionId": session_id,
        "recordIndex": unparsed["recordIndex"],
        "recordType": unparsed["recordType"],
        "redactedPayload": redaction.payload,
    }
    if unparsed.get("recordSubtype") is not None:
        core["recordSubtype"] = unparsed["recordSubtype"]

    redacted_record_hash = domain_hash("redacted-record", {"core": core})
    opaque_id = domain_hash("opaque-id", {
        "source": source, "sessionId": session_id, "recordIndex": unparsed["recordIndex"],
        "redactedRecordHash": redacted_record_hash, "schemaVersion": schema_version,
    })
    redacted_payload_hash = domain_hash("redacted-payload", {"payload": redaction.payload})
    envelope = {**core, "redactedRecordHash": redacted_record_hash, "opaqueId": opaque_id}
    triple = {"opaqueId": opaque_id, "redactedRecordHash": redacted_record_hash, "redactedPayloadHash": redacted_payload_hash}
    return envelope, triple, redaction.vault_entries


def _evidence_boundary(mode: str, event_lines: list, git_facts: dict) -> dict:
    if mode == CLAUDE_LEDGER:
        stamps = sorted(normalize_ts(line["ts"]) for line in event_lines if line.get("ts"))
        window = {"firstNativeEventTs": stamps[0], "lastNativeEventTs": stamps[-1]} if stamps else {}
        return {"mode": CLAUDE_LEDGER, "sessionWindow": window}
    return {
        "mode": GIT_ONLY_EVIDENCE,
        "headSha": git_facts.get("headSha"),
        "branch": git_facts.get("branch"),
        "workingTreeFiles": sorted(git_facts.get("workingTreeFiles", [])),
    }


def _session_include(summary: dict) -> dict:
    keep = ("source", "sessionId", "sourceVersion", "sourceRecordCount", "parsedSourceRecordCount",
            "eventCount", "knownNoiseCount", "knownNoiseCountsByType", "unparsedRecordCount",
            "compactionBoundaryCount", "thinkingSignatureOmittedCount")
    out = {k: summary.get(k) for k in keep}
    out["unparsedTypes"] = sorted(summary.get("unparsedTypes", []))
    out["unparsedAcknowledgedTypes"] = sorted(summary.get("unparsedAcknowledgedTypes", []))
    return out


def build_snapshot(*, schema_version: int, spec_version: str, repo_fingerprint: dict, mode: str,
                   event_lines: list, sessions: list, unparsed_by_session: dict, git_changesets: list,
                   git_facts: dict, redaction_summary: dict, gate_results: list) -> Snapshot:
    # item 5 — committed events: every events.jsonl line carries the SAME repositoryIdentity
    # object as item 3 (byte-identical in every line and the manifest); id + eventRecordHash sorted by id
    events_sorted = [
        {**line, "repoFingerprint": repo_fingerprint}
        for line in sorted(event_lines, key=lambda line: line["id"])
    ]
    events_include = [{"id": line["id"], "eventRecordHash": event_record_hash(line)} for line in events_sorted]

    # item 10 — unparsed opaque envelopes
    envelopes, triples, vault = [], [], []
    for (source, session_id), records in unparsed_by_session.items():
        for record in records:
            envelope, triple, entries = build_unparsed_envelope(record, source, session_id, schema_version)
            envelopes.append(envelope)
            triples.append(triple)
            vault.extend(entries)
    envelopes.sort(key=lambda e: e["opaqueId"])
    triples.sort(key=lambda t: t["opaqueId"])

    evidence_boundary = _evidence_boundary(mode, events_sorted, git_facts)

    include = {
        "schemaVersion": schema_version,
        "specVersion": spec_version,
        "repoFingerprint": repo_fingerprint,
        "mode": mode,
        "events": events_include,
        "sessions": sorted((_session_include(s) for s in sessions), key=lambda s: (s["source"], s["sessionId"])),
        "gitChangeSets": sorted(git_changesets, key=lambda c: c["commitSha"]),
        "evidenceBoundary": evidence_boundary,
        "redactionSummary": redaction_summary,
        "gateResults": gate_results,
        "unparsed": triples,
    }
    ledger_state_hash = domain_hash("ledger-state", include)

    manifest = {**include, "ledgerStateHash": ledger_state_hash, "includeFieldOrder": list(include.keys())}

    return Snapshot(
        ledger_state_hash=ledger_state_hash,
        events_bytes=_jsonl(events_sorted),
        unparsed_bytes=_jsonl(envelopes),
        manifest_bytes=canonical_bytes(manifest) + b"\n",
        vault_entries=tuple(vault),
    )
