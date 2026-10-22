"""Canonical JSON, shared by both implementations.

Both the toy and the native implementation read and write JSON through this
module, so that malformed input is rejected identically. Only the
mathematical validation (is this an element of the group?) is done separately
by each implementation.

Canonical JSON text has sorted keys, no whitespace, integers as JSON integers
and no floats. Integers with at least :data:`MAX_DIGITS` decimal digits raise
:class:`~arithkit_api.errors.JsonIntTooLargeError` (this stays below Python's
default limit of 4300 digits for int/str conversion, which is never changed).
"""

from __future__ import annotations

import json
from typing import cast

from arithkit_api.errors import JsonFormatError, JsonIntTooLargeError

MAX_DIGITS = 4000
"""Integers with this many decimal digits or more are refused."""

_LIMIT = 10 ** (MAX_DIGITS - 1)


def _parse_int(token: str) -> int:
    if len(token.lstrip("-")) >= MAX_DIGITS:
        raise JsonIntTooLargeError(f"integer with {len(token)} characters in JSON")
    return int(token)


def _reject_float(token: str) -> object:
    raise JsonFormatError(f"floats are not allowed in JSON: {token}")


def _reject_constant(token: str) -> object:
    raise JsonFormatError(f"constant {token} is not allowed in JSON")


def loads(text: object) -> object:
    """Parse JSON text, refusing floats, NaN/Infinity and too large integers."""
    if not isinstance(text, str):
        raise TypeError(f"JSON text must be a str, not {type(text).__name__}")
    try:
        return json.loads(
            text,
            parse_int=_parse_int,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as exc:
        raise JsonFormatError(str(exc)) from exc


def _check_ints(obj: object) -> None:
    if isinstance(obj, bool) or obj is None or isinstance(obj, str):
        return
    if isinstance(obj, int):
        if abs(obj) >= _LIMIT:
            raise JsonIntTooLargeError("integer too large for JSON")
        return
    if isinstance(obj, list | tuple):
        for item in cast("list[object] | tuple[object, ...]", obj):
            _check_ints(item)
        return
    if isinstance(obj, dict):
        for item in cast("dict[object, object]", obj).values():
            _check_ints(item)
        return
    raise TypeError(f"cannot encode {type(obj).__name__} as JSON")


def dumps(obj: object) -> str:
    """Canonical JSON text of ``obj`` (sorted keys, no whitespace)."""
    _check_ints(obj)
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False)


# ---------------------------------------------------------------------------
# Shape validation of decoded JSON values. These functions check the shape and
# the ranges of the data; they do not check group membership.
# ---------------------------------------------------------------------------


def expect_int(value: object, what: str) -> int:
    """``value`` as an int; booleans are not integers here."""
    if type(value) is not int:
        raise JsonFormatError(f"{what} must be an integer")
    return value


def expect_list(value: object, length: int | None, what: str) -> list[object]:
    """``value`` as a list, optionally of the given length."""
    if type(value) is not list:
        raise JsonFormatError(f"{what} must be a list")
    items: list[object] = value  # pyright: ignore[reportUnknownVariableType]
    if length is not None and len(items) != length:
        raise JsonFormatError(f"{what} must have length {length}")
    return items


def expect_dict(value: object, keys: set[str], what: str) -> dict[str, object]:
    """``value`` as a dict with exactly the given keys."""
    if type(value) is not dict:
        raise JsonFormatError(f"{what} must be an object")
    items: dict[str, object] = value  # pyright: ignore[reportUnknownVariableType]
    if set(items) != keys:
        raise JsonFormatError(f"{what} must have exactly the keys {sorted(keys)}")
    return items


QUOTIENT_TYPES = ("AdelicQuotient", "LiftedQuotient")


def decode_quotient(value: object) -> tuple[str, int, int]:
    """Decode the JSON value of a quotient parent to ``(type, N, M)``.

    The ranges of ``N`` and ``M`` are checked by the constructors.
    """
    d = expect_dict(value, {"type", "v", "N", "M"}, "quotient")
    kind = d["type"]
    if kind not in QUOTIENT_TYPES:
        raise JsonFormatError(f"unknown quotient type {kind!r}")
    if expect_int(d["v"], "format version") != 1:
        raise JsonFormatError("unsupported format version")
    assert isinstance(kind, str)
    return kind, expect_int(d["N"], "N"), expect_int(d["M"], "M")


def encode_quotient(kind: str, n: int, m: int) -> dict[str, object]:
    """JSON value of a quotient parent."""
    return {"type": kind, "v": 1, "N": n, "M": m}


def decode_element(value: object, n: int, m: int) -> tuple[int, tuple[int, int, int, int]]:
    """Decode ``[e, [a, b, c, d]]`` with ``e`` a positive divisor of ``n`` and ``0 <= a, b, c, d < m``.

    Only canonical encodings are accepted. Whether ``ad - nbc`` is a unit (or 1)
    modulo ``m`` is checked by the implementations.
    """
    pair = expect_list(value, 2, "element")
    e = expect_int(pair[0], "type e")
    if e < 1 or n % e != 0:
        raise JsonFormatError("type e must be a positive divisor of N")
    coords = expect_list(pair[1], 4, "coordinates")
    a, b, c, d = (expect_int(x, "coordinate") for x in coords)
    for x in (a, b, c, d):
        if not 0 <= x < m:
            raise JsonFormatError("coordinates must lie in [0, M)")
    return e, (a, b, c, d)


def encode_element(e: int, u: tuple[int, int, int, int]) -> list[object]:
    """JSON value ``[e, [a, b, c, d]]`` of an element relative to its parent."""
    return [e, list(u)]


def decode_subgroup(value: object) -> tuple[object, list[object]]:
    """Split the JSON value of a subgroup into the parent value and the list of generator values."""
    d = expect_dict(value, {"parent", "gens"}, "subgroup")
    return d["parent"], expect_list(d["gens"], None, "generators")
