"""Tier-A redaction families (§6.5) — a precedence-ordered registry of pure matchers.

Each family yields ``(start, end)`` byte/char spans WITHIN a single string. Overlap is
resolved leftmost-longest under the fixed precedence below (lower number = higher
precedence). The families are exactly the §6.5 floor — no entropy/shape flagging (that is
tier-B, deferred to v0.0.2).

Family precedence (§6.5(3)):
    PEM > provider-key-prefix > bearer > connection-string-userinfo > JWT > credential-keyword

(``bearer`` sits above ``jwt`` so a ``Bearer <jwt>`` redacts as the single outer span; the
spec's ladder does not rank bearer explicitly, so this placement is locked by golden test.)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

__all__ = ["KEYWORDS", "Family", "FAMILIES"]

# §6.5(c): whole trailing `_`/`.`-segment keywords. NEVER bare `key`; `token` is singular
# (so `tokens` never matches). Only the multi-segment `*_key` forms are included.
KEYWORDS = (
    "password",
    "passwd",
    "pwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "access_key",
    "secret_key",
    "private_key",
    "client_secret",
)
# longest-first so the alternation prefers the longest keyword at a position
_KW_ALT = "|".join(sorted(KEYWORDS, key=len, reverse=True))

# (a) high-confidence live secrets
PEM_RE = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----",
    re.DOTALL,
)
PROVIDER_RE = re.compile(r"sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}")
BEARER_RE = re.compile(r"Bearer\s+([A-Za-z0-9._~+/\-]+=*)")  # redact the token (group 1)
# JWT anchored to the FULL three-segment eyJ….eyJ….… shape (no bare-eyJ false positive)
JWT_RE = re.compile(r"eyJ[A-Za-z0-9_\-]+\.eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+")

# (b) connection-string userinfo: scheme://user:password@host → redact userinfo (group 1)
CONN_RE = re.compile(
    r"(?i)(?:postgresql|postgres|mysql|mongodb|redis|amqp|https|http)://([^@/\s]+)@"
)

# (c) credential-keyword assignment: left-bounded by start/quote/`export `/`_`/`.` (NOT \b),
# right-bounded by optional closing quote then `[:=]`; redact the value (group 1).
CRED_RE = re.compile(
    r"(?i)(?:^|['\"]|export\s|[._])(?:" + _KW_ALT + r")['\"]?\s*[:=]\s*['\"]?([^\s'\"]+)"
)


@dataclass(frozen=True)
class Family:
    type: str
    precedence: int
    find: Callable[[str], list]


def _whole(rx: re.Pattern) -> Callable[[str], list]:
    return lambda s: [m.span() for m in rx.finditer(s)]


def _group1(rx: re.Pattern) -> Callable[[str], list]:
    return lambda s: [m.span(1) for m in rx.finditer(s)]


FAMILIES = (
    Family("pem", 0, _whole(PEM_RE)),
    Family("provider_key", 1, _whole(PROVIDER_RE)),
    Family("bearer", 2, _group1(BEARER_RE)),
    Family("connection_string", 3, _group1(CONN_RE)),
    Family("jwt", 4, _whole(JWT_RE)),
    Family("credential_keyword", 5, _group1(CRED_RE)),
)
