"""SCENARIO: the §17 task-10 SECRET corpus — the redaction floor's acceptance story.

A developer's Claude session contains live secrets, non-secret look-alikes, and the
honest residual. After redaction: every matched secret VALUE is neutralized to a disclosed
placeholder, no original literal survives in the redacted payload OR in any marker, the
non-secret look-alikes are untouched, and identity is location-derived (the no-oracle
property). This is the founder's review surface for the safety floor.
"""

from __future__ import annotations

import pytest

from openproof.canonical.encoding import canonical_str
from openproof.redaction import redact


def r(payload, **kw):
    kw.setdefault("source", "claude_jsonl")
    kw.setdefault("session_id", "s1")
    kw.setdefault("record_index", 0)
    return redact(payload, **kw)


# --- the canonical underscore-prefixed env-var forms (the dominant real shape) ---
ENV_FORMS = [
    "TUSHARE_TOKEN=abc123",
    "OPENAI_API_KEY=abc123",
    "DB_PASSWORD=abc123",
    "CLIENT_SECRET=abc123",
    "export TUSHARE_TOKEN=abc123",
    "TUSHARE_TOKEN: abc123",
    '"TUSHARE_TOKEN": "abc123"',
]


@pytest.mark.parametrize("form", ENV_FORMS)
def test_each_env_var_form_redacts_the_value(form):
    res = r({"line": form})
    assert len(res.markers) == 1
    assert "abc123" not in res.payload["line"]
    assert "<REDACTED:credential_keyword#0>" in res.payload["line"]


def test_each_redaction_family_present(fake):
    record = {
        "pem": fake.pem("MIIabc"),
        "provider": fake.provider_key("sk-", 30),
        "bearer": "Authorization: " + fake.bearer("tok_abc_def"),
        "conn": fake.conn(user="user", pw="secretpw", host="db:5432", tail="/app"),
        "jwt": "id=" + fake.jwt("hdr", "pld", "sigpart"),
        "cred": "TUSHARE_TOKEN=abc123",
    }
    res = r(record)
    types = {m.type for m in res.markers}
    assert types == {"pem", "provider_key", "bearer", "connection_string", "jwt", "credential_keyword"}


def test_no_original_literal_survives_anywhere():
    record = {f"f{i}": form for i, form in enumerate(ENV_FORMS)}
    record["secret"] = "sk-" + "Z" * 40
    res = r(record)
    blob = canonical_str(res.payload) + "".join(m.placeholder_id + m.field_path for m in res.markers)
    assert "abc123" not in blob
    assert ("sk-" + "Z" * 40) not in blob
    # but the vault keeps each original (reversible, local-only)
    assert any(v.original == "abc123" for v in res.vault_entries)


def test_non_secret_lookalikes_not_over_redacted():
    for clean in ("total_tokens: 512", "tokens: 5", "SECRET_PATTERNS: [a, b]", "is_key: true"):
        res = r({"line": clean})
        assert res.markers == (), clean
        assert res.payload["line"] == clean


def test_honest_residual_documented_not_caught():
    # §6.5(c) deliberately does NOT reach these — covered by the layered defense
    for residual in ("TOKEN_DEFAULT=abc123", 'os.environ.get("X", "abc123")'):
        res = r({"line": residual})
        assert res.markers == (), residual


def test_no_oracle_same_redacted_state_same_bytes():
    a = r({"line": "TUSHARE_TOKEN=secret-A"})
    b = r({"line": "TUSHARE_TOKEN=secret-BBBBBB"})
    assert canonical_str(a.payload) == canonical_str(b.payload)
    assert a.markers[0].placeholder_id == b.markers[0].placeholder_id
    # and no committed-facing field embeds a value-derived id
    assert "secret-A" not in (a.markers[0].placeholder_id)


def test_same_secret_two_locations_distinct_resolvable_ids():
    res = r({"a": "token=same", "b": "token=same"})
    ids = [m.placeholder_id for m in res.markers]
    assert len(set(ids)) == 2  # location-derived, independently citeable


def test_bare_eyj_not_a_false_jwt_positive():
    res = r({"line": "eyJustABase64LookingWord"})
    assert res.markers == ()
