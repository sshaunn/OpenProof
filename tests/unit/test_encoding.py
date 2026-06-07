"""Unit tests for the §12c canonical encoding.

Non-ASCII test data is built with ``chr()`` (pure-ASCII source) so it cannot be
silently re-normalized by an editor/tool — which would otherwise defeat the NFC tests.
"""

from __future__ import annotations

import pytest

from openproof.canonical.encoding import (
    CanonicalEncodingError,
    canonical_bytes,
    canonical_str,
)

E_ACUTE = chr(0x00E9)  # composed "é"
E_PLUS_COMBINING = "e" + chr(0x0301)  # decomposed "e" + combining acute; NFC → U+00E9
CJK = chr(0x65E5) + chr(0x672C) + chr(0x8A9E)  # "日本語"


def test_keys_sorted_by_code_point():
    assert canonical_str({"b": 1, "a": 2, "c": 3}) == '{"a":2,"b":1,"c":3}'


def test_nested_objects_sorted_arrays_ordered():
    assert (
        canonical_str({"x": [3, 1, 2], "y": {"b": 1, "a": 2}})
        == '{"x":[3,1,2],"y":{"a":2,"b":1}}'
    )


def test_non_ascii_raw_utf8_no_escapes():
    assert canonical_str({"k": "caf" + E_ACUTE}) == '{"k":"caf' + E_ACUTE + '"}'
    assert canonical_str(CJK) == '"' + CJK + '"'
    # bytes carry raw UTF-8, never a \u escape sequence
    assert b"\\u" not in canonical_bytes({"k": CJK})


def test_slash_not_escaped():
    assert canonical_str("a/b") == '"a/b"'


def test_minimal_escapes():
    assert canonical_str('"\\') == '"\\"\\\\"'  # input: quote + backslash
    assert canonical_str("tab\tnl\n") == '"tab\\tnl\\n"'
    assert canonical_str("\x00\x1f") == '"\\u0000\\u001f"'


def test_bool_null_number_members():
    assert (
        canonical_str({"t": True, "f": False, "n": None, "i": 5})
        == '{"f":false,"i":5,"n":null,"t":true}'
    )


def test_nfc_normalizes_decomposed_to_composed():
    assert canonical_str(E_PLUS_COMBINING) == canonical_str(E_ACUTE)
    assert canonical_str(E_PLUS_COMBINING) == '"' + E_ACUTE + '"'


def test_nfc_key_collision_fails_closed():
    # two sibling keys that are distinct lexemes but NFC-collide must fail closed
    with pytest.raises(CanonicalEncodingError):
        canonical_str({E_ACUTE: 1, E_PLUS_COMBINING: 2})


def test_canonical_bytes_no_trailing_newline():
    out = canonical_bytes({"a": 1})
    assert out == b'{"a":1}'
    assert not out.endswith(b"\n")


def test_non_encodable_type_rejected():
    with pytest.raises(CanonicalEncodingError):
        canonical_str({"k": object()})


def test_non_string_object_key_rejected():
    with pytest.raises(CanonicalEncodingError):
        canonical_str({1: "x"})


def test_tuple_encoded_like_array():
    assert canonical_str((1, 2, 3)) == "[1,2,3]"


def test_nested_empty_containers():
    assert canonical_str({"a": {}, "b": []}) == '{"a":{},"b":[]}'


def test_keys_sorted_by_code_point_not_utf16_code_units():
    # The single most interop-critical §12c rule: "code point, NOT UTF-16 code units".
    # U+FFFF (BMP) must sort BEFORE U+10000 (astral) by code point. A UTF-16-code-unit
    # sort would invert this (U+10000's leading surrogate unit 0xD800 < 0xFFFF), so this
    # is the only assertion that distinguishes a correct impl from a JCS/UTF-16 regression.
    bmp, astral = chr(0xFFFF), chr(0x10000)
    assert canonical_str({astral: 1, bmp: 2}) == '{"' + bmp + '":2,"' + astral + '":1}'


def test_nfc_normalizes_key_before_sorting():
    # A decomposed key is emitted COMPOSED (U+00E9) and sorts by that composed code point
    # (233 > ord('z')==122 → lands AFTER 'z'). A mutant that normalized keys only for the
    # collision check but sorted/emitted the raw decomposed form would start the key with
    # 'e' (101) and place it BEFORE 'z' — byte-different output this assertion catches.
    assert canonical_str({E_PLUS_COMBINING: 1, "z": 2}) == '{"z":2,"' + E_ACUTE + '":1}'
