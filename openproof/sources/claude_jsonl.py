"""The Claude Code JSONL normalizer (§6 item 2, §17 task 4) — the only v0.1 source.

Maps real Claude session records into normalized events under the frozen content-block
rule, routing every record to exactly one of: parsed (≥1 event), known-noise (filtered),
or unparsed (surfaced, never dropped).

Content-block rule (§6 item 2):
  * an ``assistant`` record's text block(s) aggregate into ONE ``assistant_msg``;
  * each ``tool_use`` block → ONE ``tool_call`` keyed by its ``tool_use.id``;
  * each ``thinking`` block → ONE ``assistant_msg`` whose payload IS the self-describing
    thinking-omission object (the thinking text AND signature are NEVER serialized);
  * a ``user`` record → a ``prompt``, or ``tool_result`` event(s) paired by ``tool_use_id``;
  * the §8 ``contentBlockIndex`` sub-anchor is added only when a record emits >1 event.
"""

from __future__ import annotations

import json

from ..canonical.numbers import RawNumber
from ..models.event import NativeAnchor, NormalizedEvent, NormalizeResult, UnparsedRecord

__all__ = ["name", "read_records", "normalize", "KNOWN_NOISE_TYPES"]

name = "claude_jsonl"

# §6 item 2: records filtered as known-noise (never evented, counted for the P2 partition).
KNOWN_NOISE_TYPES = frozenset(
    {"permission-mode", "file-history-snapshot", "last-prompt", "queue-operation", "attachment", "ai-title"}
)


def read_records(text: str) -> list:
    """Parse JSONL into native records, preserving exact number tokens (§22.9) so a later
    canonical hash never silently collapses a distinct source integer."""
    return [
        json.loads(line, parse_int=RawNumber, parse_float=RawNumber)
        for line in text.splitlines()
        if line.strip()
    ]


def _thinking_payload(block: dict) -> dict:
    """The self-describing thinking-omission object, DERIVED per source block."""
    text_present = bool(block.get("thinking"))
    signature_present = bool(block.get("signature"))
    omitted = (["thinking"] if text_present else []) + (["signature"] if signature_present else [])
    return {
        "blockType": "thinking",
        "thinkingTextPresent": text_present,
        "thinkingTextCommitted": False,
        "opaqueSignaturePresent": signature_present,
        "opaqueSignatureCommitted": False,
        "omittedFields": omitted,
    }


def _content_blocks(record: dict) -> list:
    content = (record.get("message") or {}).get("content")
    return content if isinstance(content, list) else []


def _normalize_assistant(record, index, session_id):
    """Return ``(events, thinking_signatures_omitted)`` for one assistant record."""
    uuid, ts = record.get("uuid"), record.get("timestamp")
    blocks = list(enumerate(_content_blocks(record)))
    texts = [(i, b) for i, b in blocks if b.get("type") == "text"]
    thinkings = [(i, b) for i, b in blocks if b.get("type") == "thinking"]
    tool_uses = [(i, b) for i, b in blocks if b.get("type") == "tool_use"]

    # provisional events as (kind, content_block_index, payload, pair_id, primary_anchor)
    provisional = []
    if texts:
        provisional.append(("assistant_msg", texts[0][0], {"text": "\n".join(b.get("text", "") for _, b in texts)}, None, uuid))
    provisional += [("assistant_msg", i, _thinking_payload(b), None, uuid) for i, b in thinkings]
    provisional += [("tool_call", i, {"name": b.get("name"), "input": b.get("input")}, b.get("id"), b.get("id")) for i, b in tool_uses]
    if not provisional:  # a recognized record must emit ≥1 event (never a silent drop)
        provisional.append(("assistant_msg", 0, {"text": ""}, None, uuid))

    multi = len(provisional) > 1
    events = tuple(
        NormalizedEvent("assistant_msg" if kind == "assistant_msg" else kind, name, session_id, index,
                        NativeAnchor(primary, cbi if multi else None), payload, ts, pair_id)
        for kind, cbi, payload, pair_id, primary in provisional
    )
    omitted = sum(1 for _, b in thinkings if b.get("signature"))
    return events, omitted


def _normalize_user(record, index, session_id):
    uuid, ts = record.get("uuid"), record.get("timestamp")
    content = (record.get("message") or {}).get("content")
    blocks = content if isinstance(content, list) else []
    tool_results = [(i, b) for i, b in enumerate(blocks) if isinstance(b, dict) and b.get("type") == "tool_result"]

    if tool_results:
        multi = len(tool_results) > 1
        return tuple(
            NormalizedEvent("tool_result", name, session_id, index,
                            NativeAnchor(uuid, i if multi else None),
                            {"content": b.get("content"), "isError": bool(b.get("is_error"))},
                            ts, b.get("tool_use_id"))
            for i, b in tool_results
        )
    if isinstance(content, list):  # user message as text blocks
        text = "\n".join(b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text")
    else:
        text = content if isinstance(content, str) else ""
    return (NormalizedEvent("prompt", name, session_id, index, NativeAnchor(uuid, None), {"content": text}, ts, None),)


# record type → handler that returns (events, signatures_omitted)
_PARSERS = {
    "assistant": _normalize_assistant,
    "user": lambda r, i, s: (_normalize_user(r, i, s), 0),
}


def normalize(records: list, *, session_id: str) -> NormalizeResult:
    events: list = []
    parsed, known_noise, unparsed = set(), set(), []
    compaction = 0
    signatures_omitted = 0

    for index, record in enumerate(records):
        rtype = record.get("type")
        parser = _PARSERS.get(rtype)
        if parser is not None:
            evs, omitted = parser(record, index, session_id)
            events.extend(evs)
            signatures_omitted += omitted
            parsed.add(index)
        elif rtype in KNOWN_NOISE_TYPES:
            known_noise.add(index)
        else:  # unknown type (system, mode, …) → surfaced, never dropped
            subtype = record.get("subtype")
            unparsed.append(UnparsedRecord(index, rtype, subtype, record))
            if rtype == "system" and subtype == "compact_boundary":  # §6 item 2: only this subtype
                compaction += 1

    return NormalizeResult(
        tuple(events), frozenset(parsed), frozenset(known_noise), tuple(unparsed), compaction, signatures_omitted
    )
