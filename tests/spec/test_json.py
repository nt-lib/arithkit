"""Canonical JSON, run against both implementations."""

from __future__ import annotations

import pytest

from arithkit_api.errors import (
    InvalidParameterError,
    JsonFormatError,
    JsonIntTooLargeError,
    NotInGroupError,
)
from conftest import Backend


def test_canonical_texts(backend: Backend) -> None:
    q = backend.quotient.GL2QSubQuotient(6, 5)
    assert q.to_json() == '{"M":5,"N":6,"type":"GL2QSubQuotient","v":1}'
    x = q.al_element(3)
    assert x.to_json() == "[3,[1,0,0,1]]"
    assert (
        x.to_json_full() == '{"element":[3,[1,0,0,1]],"parent":{"M":5,"N":6,"type":"GL2QSubQuotient","v":1}}'
    )
    h = q.subgroup([x])
    assert h.to_json().startswith('{"gens":[')


def test_round_trips(backend: Backend) -> None:
    for cls in (backend.quotient.GL2ASubQuotient, backend.quotient.GL2QSubQuotient):
        q = cls(10, 3)
        assert backend.quotient.quotient_from_json(q.to_json()) == q
        for x in q.elements()[::17]:
            assert q.element_from_json(x.to_json()) == x
        h = q.subgroup(q.elements()[5:8])
        assert backend.subgroup.subgroup_from_json(h.to_json()) == h


def test_malformed_json(backend: Backend) -> None:
    q = backend.quotient.GL2ASubQuotient(6, 5)
    for text in [
        "",
        "[",
        "[1,[1,0,0,1]] x",
        "[1.0,[1,0,0,1]]",
        "[1,[1,0,0,1.5]]",
        "[true,[1,0,0,1]]",
        "[1,[1,0,0]]",
        "[1,[1,0,0,1,0]]",
        "[1,[5,0,0,1]]",
        "[1,[-1,0,0,1]]",
        "[4,[1,0,0,1]]",
        "[0,[1,0,0,1]]",
        '{"e":1}',
        "NaN",
        "[1,[1,0,0,Infinity]]",
    ]:
        with pytest.raises(JsonFormatError):
            q.element_from_json(text)
    with pytest.raises(JsonIntTooLargeError):
        q.element_from_json("[1,[" + "1" * 4000 + ",0,0,1]]")
    with pytest.raises(JsonFormatError):
        q.element_from_json("[1,[" + "1" * 3999 + ",0,0,1]]")
    with pytest.raises(NotInGroupError):
        q.element_from_json("[1,[0,0,0,0]]")
    with pytest.raises(TypeError):
        q.element_from_json(b"[1,[1,0,0,1]]")  # pyright: ignore[reportArgumentType]
    for text in [
        '{"M":5,"N":6,"type":"Other","v":1}',
        '{"M":5,"N":6,"type":"GL2ASubQuotient","v":2}',
        '{"M":5,"N":6,"type":"GL2ASubQuotient"}',
        '{"M":5,"N":6.0,"type":"GL2ASubQuotient","v":1}',
        '{"M":5,"N":6,"type":"GL2ASubQuotient","v":1,"x":0}',
    ]:
        with pytest.raises(JsonFormatError):
            backend.quotient.quotient_from_json(text)
    with pytest.raises(InvalidParameterError):
        backend.quotient.quotient_from_json('{"M":5,"N":4,"type":"GL2ASubQuotient","v":1}')
    with pytest.raises(JsonFormatError):
        backend.subgroup.subgroup_from_json('{"gens":[[1,[1,0,0,1]]]}')
