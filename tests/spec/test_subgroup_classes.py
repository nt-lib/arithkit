"""Centres, centred subgroups and classes of subgroups of bounded index, for both implementations."""

from __future__ import annotations

from typing import Any

import pytest

from arithkit_api.errors import InvalidParameterError
from conftest import Backend

BASE = (0, 0, 0)  # the base vertex
STD = (-1, 0, 0)  # o(p)_p, the other end of the standard edge


# Class counts of Magma's Subgroups(G : IndexLimit := I) for G = GL_2(Z/n) and SL_2(Z/n),
# which are the adelic and the lifted quotient for N = 1.
MAGMA_COUNTS = [
    ("GL", 2, 6, 4),
    ("SL", 2, 6, 4),
    ("GL", 3, 48, 16),
    ("SL", 3, 48, 7),
    ("GL", 4, 30, 54),
    ("SL", 4, 30, 18),
    ("GL", 5, 30, 25),
    ("SL", 5, 30, 9),
    ("SL", 6, 20, 22),
    ("SL", 9, 15, 10),
]


def parent(backend: Backend, kind: str, n: int, m: int) -> Any:
    cls = backend.quotient.GL2ASubQuotient if kind == "GL" else backend.quotient.GL2QSubQuotient
    return cls(n, m)


@pytest.mark.parametrize(("kind", "n", "bound", "count"), MAGMA_COUNTS)
def test_class_counts_match_magma(backend: Backend, kind: str, n: int, bound: int, count: int) -> None:
    classes = parent(backend, kind, 1, n).subgroup_classes(bound)
    assert len(classes) == count


def conjugates(q: Any, h: Any) -> set[frozenset[Any]]:
    els = h.elements()
    return {frozenset(g * x * g.inverse() for x in els) for g in q.elements()}


@pytest.mark.parametrize(("kind", "n", "m", "bound"), [("GL", 1, 3, 48), ("SL", 2, 3, 12), ("GL", 3, 3, 12)])
def test_representatives_are_canonical(backend: Backend, kind: str, n: int, m: int, bound: int) -> None:
    q = parent(backend, kind, n, m)
    classes = q.subgroup_classes(bound)
    keys = [(h.index(), [x.coordinates() for x in h.gens()]) for h in classes]
    assert keys == sorted(keys)
    seen: set[frozenset[Any]] = set()
    for h in classes:
        assert h.index() <= bound
        conj = conjugates(q, h)
        assert not conj & seen, "two representatives are conjugate"
        seen |= conj
        least = min(
            (sorted(q.subgroup(c).gens(), key=lambda x: x.coordinates()) for c in conj),
            key=lambda gens: [x.coordinates() for x in gens],
        )
        assert [x.coordinates() for x in h.gens()] == [x.coordinates() for x in least]
        assert h.is_centred() == all(q.subgroup(c).is_centred() for c in conj)


def test_index_one_and_invalid_bound(backend: Backend) -> None:
    q = backend.quotient.GL2ASubQuotient(2, 3)
    (whole,) = q.subgroup_classes(1)
    assert whole.order() == q.order()
    with pytest.raises(InvalidParameterError):
        q.subgroup_classes(0)
    with pytest.raises(TypeError):
        q.subgroup_classes(2.5)


def gamma0(q: Any, level: int) -> Any:
    """The image of Gamma_0(level) in the quotient for N = 1: lower left entry divisible by level."""
    return q.subgroup(x for x in q.elements() if x.coordinates()[1][2] % level == 0)


def test_centring_examples() -> None:
    """ex:centring-examples and ex:centred-levels, for p = 3 (only small groups: toy speed)."""
    from conftest import load_backend

    for backend in (load_backend("toy"),):
        q9 = backend.quotient.GL2ASubQuotient(1, 9)
        g9 = gamma0(q9, 9)
        assert g9.centre() == ((3, STD, STD),)  # the snake o - o(3) - o(9) has centre o(3)
        assert g9.helling_level() == 1 and not g9.is_centred()
        conj = q9.subgroup(
            x for x in q9.elements() if x.coordinates()[1][1] % 3 == 0 and x.coordinates()[1][2] % 3 == 0
        )
        assert conj.is_centred() and conj.helling_level() == 1 and conj.principal_level() == 3
        q3 = backend.quotient.GL2ASubQuotient(1, 3)
        g3 = gamma0(q3, 3)
        assert g3.centre() == ((3, STD, BASE),) and g3.helling_level() == 3 and not g3.is_centred()


@pytest.mark.parametrize("p", [2, 3, 5])
def test_gamma0_p_is_centred_at_level_p(backend: Backend, p: int) -> None:
    """Gamma0^(p) (type 1 part of U_p) is centred of Helling level p (ex:centring-examples (1))."""
    q = backend.quotient.GL2ASubQuotient(p, p)
    h = q.subgroup(x for x in q.elements() if x.type() == 1)
    assert h.is_centred() and h.helling_level() == p and h.al_image() == (1,)
    star = q.subgroup(q.elements())
    assert star.is_centred() and star.al_image() == (1, p) and star.principal_level() == 1


def test_trivial_and_whole_subgroups(backend: Backend) -> None:
    for q in (backend.quotient.GL2ASubQuotient(6, 4), backend.quotient.GL2QSubQuotient(10, 3)):
        trivial = q.subgroup([])
        assert trivial.is_centred() and trivial.principal_level() == q.M
        whole = q.subgroup(q.elements())
        assert whole.is_centred() and whole.principal_level() == 1
        primes = [
            p for p in range(2, q.N * q.M + 1) if (q.N * q.M) % p == 0 and all(p % d for d in range(2, p))
        ]
        assert [entry[0] for entry in trivial.centre()] == primes


def test_centred_classes(backend: Backend) -> None:
    q = backend.quotient.GL2ASubQuotient(1, 2)  # S_3: the Borel subgroup is the image of Gamma_0(2)
    classes = q.subgroup_classes(6)
    centred = q.centred_subgroup_classes(6)
    assert [h.order() for h in classes] == [6, 3, 2, 1]
    assert [h.order() for h in centred] == [6, 3, 1]
    (borel,) = [h for h in classes if h.order() == 2]
    assert borel.helling_level() == 2 and not borel.is_centred()
