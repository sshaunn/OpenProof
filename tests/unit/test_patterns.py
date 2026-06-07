"""Unit tests for the §6.5 tier-A redaction families (regex behavior)."""

from __future__ import annotations

from openproof.redaction.patterns import CRED_RE, FAMILIES, JWT_RE, KEYWORDS, PROVIDER_RE


def _find(fam_type):
    fam = next(f for f in FAMILIES if f.type == fam_type)
    return lambda s: fam.find(s)


def test_provider_prefixes():
    assert _find("provider_key")("sk-" + "A" * 30)
    assert _find("provider_key")("AKIA" + "B" * 16)
    assert _find("provider_key")("ghp_" + "c" * 36)
    assert not _find("provider_key")("sk-short")  # < 20 chars after sk-


def test_jwt_requires_full_three_segments(fake):
    assert JWT_RE.search(fake.jwt("abc", "def", "sig123"))
    assert not JWT_RE.search("eyJ" + "ustAWordNotAJwt")  # bare eyJ is not a JWT
    assert not JWT_RE.search("eyJ" + "only.onesegment")


def test_pem_block_matched_whole(fake):
    assert _find("pem")("prefix " + fake.pem("MIIABC") + " suffix")


def test_connection_string_userinfo_group(fake):
    s = fake.conn(user="user", pw="pass", host="host:5432", tail="/db")  # a postgres-style URL w/ userinfo
    spans = _find("connection_string")(s)
    # the span must be EXACTLY the userinfo (user:pass), not the whole URL — a _whole(CONN_RE)
    # mutation would over-redact the scheme/host and this asserts against that
    assert spans == [(11, 20)]
    assert s[spans[0][0]:spans[0][1]] == "user:pass"


def test_credential_keyword_matches_underscore_env_forms():
    for form in (
        "TUSHARE_TOKEN=abc123",
        "OPENAI_API_KEY=abc123",
        "DB_PASSWORD=abc123",
        "CLIENT_SECRET=abc123",
        "export TUSHARE_TOKEN=abc123",
        "TUSHARE_TOKEN: abc123",
        '"TUSHARE_TOKEN": "abc123"',
    ):
        assert CRED_RE.search(form), form


def test_credential_keyword_negatives_do_not_fire():
    for form in ("total_tokens: 512", "tokens: 5", "SECRET_PATTERNS: [a]", "is_key: true", "section_key: x"):
        assert not CRED_RE.search(form), form


def test_credential_keyword_honest_residual_not_caught():
    # leading-segment key and a non-assignment arg-default are outside §6.5(c) by design
    assert not CRED_RE.search("TOKEN_DEFAULT=abc123")
    assert not CRED_RE.search('os.environ.get("X", "abc123")')


def test_keyword_set_is_frozen():
    assert "token" in KEYWORDS and "key" not in KEYWORDS  # singular token; never bare key
    assert all(k == k.lower() for k in KEYWORDS)
