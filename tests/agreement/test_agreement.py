"""Toy versus native: random inputs, identical outcomes (values or exception classes)."""

from __future__ import annotations

import functools
import random
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from conftest import Backend, load_backend
from helpers import outcome, random_gamma0_star

pytestmark = pytest.mark.native


@functools.cache
def backends() -> tuple[Backend, Backend]:
    """Toy and native backends, imported lazily so that collection works without the extension."""
    return load_backend("toy"), load_backend("native")


SQUAREFREE = [1, 2, 3, 5, 6, 7, 10, 11, 14, 15, 21, 30]
small_int = st.integers(min_value=-(10**20), max_value=10**20)
any_int = st.one_of(small_int, st.integers(min_value=-(2**70), max_value=2**70))
kinds = st.sampled_from(["GL2ASubQuotient", "GL2QSubQuotient"])
levels = st.tuples(st.sampled_from(SQUAREFREE), st.integers(min_value=1, max_value=13), kinds)


def pair(n: int, m: int, kind: str) -> tuple[Any, Any]:
    toy, native = backends()
    return getattr(toy.quotient, kind)(n, m), getattr(native.quotient, kind)(n, m)


def coords(x: object) -> object:
    return x.coordinates() if hasattr(x, "coordinates") else x  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType, reportUnknownVariableType]


def random_element_args(rnd: random.Random, n: int, m: int) -> tuple[int, tuple[int, int, int, int]]:
    divisors = [d for d in range(1, n + 1) if n % d == 0]
    return rnd.choice(divisors), tuple(rnd.randrange(-3 * m, 3 * m) for _ in range(4))  # pyright: ignore[reportReturnType]


@given(levels, st.integers(min_value=0, max_value=2**32))
def test_group_law(level: tuple[int, int, str], seed: int) -> None:
    n, m, kind = level
    toy, native = pair(n, m, kind)
    rnd = random.Random(seed)
    xs_toy, xs_native = [], []
    for _ in range(4):
        e, u = random_element_args(rnd, n, m)
        a, b = outcome(lambda: toy(e, u)), outcome(lambda: native(e, u))  # noqa: B023
        assert (a[0], coords(a[1])) == (b[0], coords(b[1]))
        if a[0] == "ok":
            xs_toy.append(a[1])
            xs_native.append(b[1])
    for x, y in zip(xs_toy, xs_native, strict=True):
        assert x.inverse().coordinates() == y.inverse().coordinates()
        assert x.det() == y.det() and x.type() == y.type()
        assert x.to_json() == y.to_json() and x.to_json_full() == y.to_json_full()
        k = rnd.randrange(-50, 50)
        assert (x**k).coordinates() == (y**k).coordinates()
        for x2, y2 in zip(xs_toy, xs_native, strict=True):
            assert (x * x2).coordinates() == (y * y2).coordinates()


@given(levels)
def test_parent_data(level: tuple[int, int, str]) -> None:
    toy, native = pair(*level)
    assert toy.order() == native.order()
    assert toy.type_group() == native.type_group()
    assert toy.to_json() == native.to_json()
    assert toy.identity().coordinates() == native.identity().coordinates()


@given(st.sampled_from(SQUAREFREE), st.integers(min_value=1, max_value=7), kinds, st.integers(0, 2**32))
def test_subgroups(n: int, m: int, kind: str, seed: int) -> None:
    toy, native = pair(n, m, kind)
    rnd = random.Random(seed)
    els_toy = toy.elements()
    els_native = native.elements()
    assert [x.coordinates() for x in els_toy] == [x.coordinates() for x in els_native]
    picks = [rnd.randrange(len(els_toy)) for _ in range(rnd.randrange(0, 3))]
    h_toy = toy.subgroup([els_toy[i] for i in picks])
    h_native = native.subgroup([els_native[i] for i in picks])
    assert h_toy.to_json() == h_native.to_json()
    assert [x.coordinates() for x in h_toy.elements()] == [x.coordinates() for x in h_native.elements()]
    assert h_toy.al_image() == h_native.al_image()
    assert h_toy.index() == h_native.index()
    for i in picks:
        assert els_toy[i].order() == els_native[i].order()


@given(st.sampled_from(SQUAREFREE), st.integers(min_value=1, max_value=40), st.integers(0, 2**32))
def test_from_matrix(n: int, m: int, seed: int) -> None:
    toy, native = pair(n, m, "GL2QSubQuotient")
    rnd = random.Random(seed)
    for _ in range(5):
        g = random_gamma0_star(rnd, n)
        if rnd.random() < 0.3:  # perturb: usually no longer in Gamma_0(N)^*
            (a, b), (c, d) = g
            g = ((a + rnd.randrange(-2, 3), b), (c, d * rnd.choice([1, 2, -1])))
        a, b = outcome(lambda: toy.from_matrix(g)), outcome(lambda: native.from_matrix(g))  # noqa: B023
        assert (a[0], coords(a[1])) == (b[0], coords(b[1]))


@given(levels, st.lists(any_int, min_size=0, max_size=6), any_int)
def test_construction_outcomes(level: tuple[int, int, str], u: list[int], e: int) -> None:
    toy, native = pair(*level)
    for args in [(e, tuple(u)), (abs(e) % 40, tuple(u)), (1, tuple(u))]:
        a = outcome(lambda: toy(*args))  # noqa: B023
        b = outcome(lambda: native(*args))  # noqa: B023
        assert (a[0], coords(a[1])) == (b[0], coords(b[1]))


@given(st.text(alphabet='[]{}0123456789,-"aeMNtvy:. ', max_size=40))
def test_json_parsing_outcomes(text: str) -> None:
    toy, native = pair(6, 5, "GL2ASubQuotient")
    a, b = outcome(lambda: toy.element_from_json(text)), outcome(lambda: native.element_from_json(text))
    assert (a[0], coords(a[1])) == (b[0], coords(b[1]))
    a = outcome(lambda: backends()[0].quotient.quotient_from_json(text).to_json())
    b = outcome(lambda: backends()[1].quotient.quotient_from_json(text).to_json())
    assert a == b


def test_mixing_backends_is_a_type_error() -> None:
    toy, native = pair(6, 5, "GL2ASubQuotient")
    x, y = toy.identity(), native.identity()
    assert x != y and y != x and toy != native
    for f in (lambda: x * y, lambda: y * x, lambda: toy.subgroup([y]), lambda: native.subgroup([x])):
        with pytest.raises(TypeError):
            f()
    assert x not in native.subgroup([]) and y not in toy.subgroup([])
