"""Behaviour of subgroups, run against both implementations."""

from __future__ import annotations

import math
import random
from typing import Any

import pytest

from arithkit_api.errors import ParentMismatchError
from conftest import Backend


def kernel(q: Any, m: int) -> Any:
    """The image of Gamma^(N; m) in Q_{N,M} for m | M: type 1 and u = 1 modulo m."""
    return q.subgroup(
        x
        for x in q.elements()
        if x.type() == 1
        and all((v - w) % m == 0 for v, w in zip(x.coordinates()[1], (1, 0, 0, 1), strict=True))
    )


def test_lcm_gcd_laws(backend: Backend) -> None:
    """prop:lcm-gcd, seen inside Q_{N,L}: intersections and products of the kernels."""
    for cls in (backend.quotient.GL2ASubQuotient, backend.quotient.GL2QSubQuotient):
        q = cls(2, 6)
        for m1, m2 in [(2, 3), (1, 6), (2, 6), (3, 6)]:
            k1, k2 = kernel(q, m1), kernel(q, m2)
            meet = q.subgroup(x for x in k1.elements() if x in k2)
            assert meet == kernel(q, math.lcm(m1, m2))
            assert q.subgroup(k1.elements() + k2.elements()) == kernel(q, math.gcd(m1, m2))


def test_index_formula(backend: Backend) -> None:
    """lem:index-formula inside Q_{N,M}: [Q : H] = 2^(omega - d) [Q^0 : H^0] with ^0 the type 1 parts."""
    rnd = random.Random(5)
    q = backend.quotient.GL2ASubQuotient(6, 5)
    q0 = sum(1 for x in q.elements() if x.type() == 1)
    els = q.elements()
    for _ in range(10):
        h = q.subgroup(rnd.sample(els, rnd.randrange(0, 3)))
        h0 = sum(1 for x in h.elements() if x.type() == 1)
        assert h.index() * len(h.al_image()) * h0 == len(q.type_group()) * q0
        assert h.index() * h.order() == q.order()


def test_canonical_generators(backend: Backend) -> None:
    rnd = random.Random(7)
    for cls in (backend.quotient.GL2ASubQuotient, backend.quotient.GL2QSubQuotient):
        q = cls(10, 3)
        els = q.elements()
        for _ in range(8):
            h = q.subgroup(rnd.sample(els, rnd.randrange(1, 4)))
            again = q.subgroup(h.gens())
            assert again == h and again.gens() == h.gens()
            assert list(h.gens()) == sorted(h.gens(), key=lambda x: x.coordinates())
            assert q.subgroup(h.elements()).gens() == h.gens()
            assert all(x in h for x in h.gens())
        trivial = q.subgroup([])
        assert trivial.order() == 1 and trivial.gens() == () and trivial.al_image() == (1,)
        whole = q.subgroup(els)
        assert whole.order() == q.order() and whole.index() == 1
        assert trivial.is_subgroup_of(whole) and not whole.is_subgroup_of(trivial)


def test_subgroup_membership_and_parents(backend: Backend) -> None:
    q = backend.quotient.GL2ASubQuotient(6, 5)
    other = backend.quotient.GL2ASubQuotient(6, 7)
    h = q.subgroup([q.al_element(2)])
    assert h.order() == q.al_element(2).order()
    assert h.al_image() == (1, 2)
    assert q.identity() in h and other.identity() not in h and 3 not in h
    assert q.identity() in h.elements()
    with pytest.raises(ParentMismatchError):
        q.subgroup([other.identity()])
    with pytest.raises(ParentMismatchError):
        h.is_subgroup_of(other.subgroup([]))
    with pytest.raises(TypeError):
        q.subgroup([1])
    assert h == q.subgroup([q.al_element(2), q.identity()])
    assert hash(h) == hash(q.subgroup([q.al_element(2)]))
    assert h != other.subgroup([other.al_element(2)])
