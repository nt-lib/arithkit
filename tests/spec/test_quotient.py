"""Behaviour of the quotient groups, run against both implementations."""

from __future__ import annotations

import itertools
import math
import random
from typing import Any

import pytest

from arithkit_api.errors import InvalidParameterError, NotInGroupError, ParentMismatchError
from conftest import Backend
from helpers import SMALL_CASES, al_matrix, mat_mul, random_gamma0_star


def groups(backend: Backend, n: int, m: int) -> list[Any]:
    return [backend.quotient.GL2ASubQuotient(n, m), backend.quotient.GL2QSubQuotient(n, m)]


@pytest.mark.parametrize(("n", "m"), SMALL_CASES)
def test_order_matches_enumeration(backend: Backend, n: int, m: int) -> None:
    for q in groups(backend, n, m):
        els = q.elements()
        assert len(els) == q.order()
        keys = [x.coordinates() for x in els]
        assert keys == sorted(keys), "elements() is in canonical order"
        assert len(set(els)) == len(els)


@pytest.mark.parametrize(("n", "m"), SMALL_CASES)
def test_group_axioms(backend: Backend, n: int, m: int) -> None:
    rnd = random.Random(n * 1000 + m)
    for q in groups(backend, n, m):
        els = q.elements()
        sample = rnd.sample(els, min(len(els), 10))
        one = q.identity()
        assert one.coordinates() == (1, (1 % m, 0, 0, 1 % m))
        for x in sample:
            assert x * one == x == one * x
            assert x * x.inverse() == one == x.inverse() * x
            assert x ** x.order() == one
            for y in sample:
                assert (x * y).type() == x.type() * y.type() // math.gcd(x.type(), y.type()) ** 2
                for z in sample[:3]:
                    assert (x * y) * z == x * (y * z)


def test_lifted_order_formula(backend: Backend) -> None:
    for n, m in [(6, 35), (30, 49), (7, 7**5), (2 * 3 * 5 * 7 * 11 * 13, 2**10 * 3**4)]:
        adelic, lifted = groups(backend, n, m)
        assert adelic.order() == lifted.order() * math.prod(p - 1 for p in _primes(m)) * m // math.prod(
            _primes(m)
        )


def _primes(m: int) -> list[int]:
    return [p for p in range(2, m + 1) if m % p == 0 and all(p % d for d in range(2, p))]


@pytest.mark.parametrize(("n", "m"), [(6, 5), (10, 4), (15, 6), (2, 8), (30, 7), (1, 12)])
def test_from_matrix_is_a_homomorphism(backend: Backend, n: int, m: int) -> None:
    q = backend.quotient.GL2QSubQuotient(n, m)
    rnd = random.Random(n + 100 * m)
    for _ in range(30):
        g, h = random_gamma0_star(rnd, n), random_gamma0_star(rnd, n)
        assert q.from_matrix(g) * q.from_matrix(h) == q.from_matrix(mat_mul(g, h))
        k = rnd.randrange(2, 7)
        assert q.from_matrix(mat_mul(((k, 0), (0, k)), g)) == q.from_matrix(g)
    for e in q.type_group():
        assert q.from_matrix(al_matrix(n, e)) == q.al_element(e)
    minus_one = q.from_matrix(((-1, 0), (0, -1)))
    assert (minus_one == q.identity()) == (m <= 2)


def test_from_matrix_rejects(backend: Backend) -> None:
    q = backend.quotient.GL2QSubQuotient(6, 5)
    for g in [((1, 0), (0, -1)), ((1, 0), (1, 1)), ((2, 0), (0, 1)), ((0, 0), (0, 0)), ((1, 0), (3, 1))]:
        with pytest.raises(NotInGroupError):
            q.from_matrix(g)
    for bad in [[[1, 0], [0, 1]], ((1, 0),), ((1, 0, 0), (0, 1)), ((1.0, 0), (0, 1)), "x"]:
        with pytest.raises(TypeError):
            q.from_matrix(bad)
    huge = 10**60
    assert q.from_matrix(((huge, 0), (0, huge))) == q.identity()


def test_prime_helling_level(backend: Backend) -> None:
    """prop:prime-helling (3): conjugation by W_p = [[0,-1],[p,0]] is (a,b,c,d) -> (d,-c,-b,a), W_p^2 = -1."""
    for p, k in [(2, 3), (3, 2), (5, 2), (7, 1)]:
        m = p**k
        q = backend.quotient.GL2QSubQuotient(p, m)
        w = q.from_matrix(((0, -1), (p, 0)))
        assert w * w == q.from_matrix(((-1, 0), (0, -1)))
        for x in q.elements():
            if x.type() != 1:
                continue
            a, b, c, d = x.coordinates()[1]
            assert w * x * w.inverse() == q(1, (d, -c, -b, a))


def test_fibre_product_orders(backend: Backend) -> None:
    """thm:fibre-product implies |Q_{N,M}| = |T_N| prod_i |Q_{N,p_i^k_i}| / |T_N|."""
    for n, m in [(6, 12), (10, 18), (15, 20), (1, 30), (30, 9 * 4 * 5)]:
        for cls in (backend.quotient.GL2ASubQuotient, backend.quotient.GL2QSubQuotient):
            t = len(cls(n, m).type_group())
            pieces = [cls(n, p**k).order() // t for p, k in _factor(m)]
            assert cls(n, m).order() == t * math.prod(pieces)


def _factor(m: int) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for p in _primes(m):
        k = 0
        while m % p == 0:
            m //= p
            k += 1
        out.append((p, k))
    return out


def test_construction_and_reduction(backend: Backend) -> None:
    q = backend.quotient.GL2ASubQuotient(6, 5)
    x = q(6, (-1, 10**30 + 1, 7, -4))
    assert x.coordinates() == (6, (4, 1, 2, 1))
    assert x == q(6, (4, 1, 2, 1))
    assert q(True, (1, 0, 0, 1)) == q.identity()
    with pytest.raises(NotInGroupError):
        q(4, (1, 0, 0, 1))
    with pytest.raises(NotInGroupError):
        q(0, (1, 0, 0, 1))
    with pytest.raises(NotInGroupError):
        q(-6, (1, 0, 0, 1))
    with pytest.raises(NotInGroupError):
        q(2**70, (1, 0, 0, 1))
    with pytest.raises(NotInGroupError):
        q(1, (0, 0, 0, 0))
    with pytest.raises(NotInGroupError):
        backend.quotient.GL2QSubQuotient(6, 5)(1, (2, 0, 0, 1))
    for bad in [[1, 0, 0, 1], (1, 0, 0), (1, 0, 0, 1, 0), (1.0, 0, 0, 1), "abcd"]:
        with pytest.raises(TypeError):
            q(1, bad)
    with pytest.raises(TypeError):
        q(1.5, (1, 0, 0, 1))
    with pytest.raises(NotInGroupError):
        q.al_element(5)


def test_invalid_parameters(backend: Backend) -> None:
    for cls in (backend.quotient.GL2ASubQuotient, backend.quotient.GL2QSubQuotient):
        for n, m in [(4, 3), (0, 3), (3, 0), (-6, 5), (6, -5), (2**63, 3), (3, 2**63), (2**200, 1)]:
            with pytest.raises(InvalidParameterError):
                cls(n, m)
        for n, m in [(6.0, 5), (6, "5"), (None, 5)]:
            with pytest.raises(TypeError):
                cls(n, m)
        assert cls(2**61 - 1, 2**63 - 1).order() > 0


def test_powers(backend: Backend) -> None:
    q = backend.quotient.GL2QSubQuotient(10, 9)
    rnd = random.Random(3)
    for x in rnd.sample(q.elements(), 15):
        assert x**0 == q.identity()
        assert x**1 == x
        assert x**-1 == x.inverse()
        assert x**-3 == (x**3).inverse()
        big = 10**40 + 7
        assert x**big == x ** (big % x.order())
        assert x ** (-big) == x ** (-(big % x.order()))
    with pytest.raises(TypeError):
        _ = q.identity() ** 1.0  # pyright: ignore[reportOperatorIssue]


def test_equality_and_hashing(backend: Backend) -> None:
    adelic = backend.quotient.GL2ASubQuotient(6, 5)
    lifted = backend.quotient.GL2QSubQuotient(6, 5)
    assert adelic == backend.quotient.GL2ASubQuotient(6, 5)
    assert hash(adelic) == hash(backend.quotient.GL2ASubQuotient(6, 5))
    assert adelic != lifted
    assert adelic != backend.quotient.GL2ASubQuotient(6, 7)
    x = lifted(6, (1, 0, 0, 1))
    assert x != adelic(6, (1, 0, 0, 1))
    assert lifted.to_adelic(x) == adelic(6, (1, 0, 0, 1))
    assert adelic.to_lifted(lifted.to_adelic(x)) == x
    assert x == lifted(6, (1, 0, 0, 1))
    assert hash(x) == hash(lifted(6, (1, 0, 0, 1)))
    assert x != (6, (1, 0, 0, 1))
    assert x != 1
    with pytest.raises(NotInGroupError):
        adelic.to_lifted(adelic(1, (2, 0, 0, 1)))
    with pytest.raises(ParentMismatchError):
        adelic.to_lifted(x)
    with pytest.raises(ParentMismatchError):
        _ = x * adelic.identity()
    with pytest.raises(TypeError):
        _ = x * 2  # pyright: ignore[reportOperatorIssue]
    with pytest.raises(TypeError):
        _ = x < x  # pyright: ignore[reportOperatorIssue]


def test_type_group_and_det(backend: Backend) -> None:
    q = backend.quotient.GL2ASubQuotient(30, 7)
    assert q.type_group() == (1, 2, 3, 5, 6, 10, 15, 30)
    assert q.N == 30 and q.M == 7
    for x in itertools.islice(q.elements(), 0, None, 997):
        a, b, c, d = x.coordinates()[1]
        assert x.det() == (a * d - 30 * b * c) % 7


def test_printing(backend: Backend) -> None:
    """Elements print without their parent; both implementations print identically."""
    q = backend.quotient.GL2QSubQuotient(6, 5)
    x = q.al_element(3)
    assert repr(x) == str(x) == "(3, (1, 0, 0, 1))"
    assert repr(q) == str(q) == "GL2QSubQuotient(6, 5)"
    assert repr(backend.quotient.GL2ASubQuotient(10, 7)) == "GL2ASubQuotient(10, 7)"
    assert repr(q.subgroup([x])) == f"subgroup of order {q.subgroup([x]).order()} of GL2QSubQuotient(6, 5)"
