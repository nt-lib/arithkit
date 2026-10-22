"""Helpers shared by the tests."""

from __future__ import annotations

import random
from collections.abc import Callable

type Mat2 = tuple[tuple[int, int], tuple[int, int]]

SMALL_CASES = [(1, 1), (1, 2), (2, 2), (6, 2), (2, 3), (3, 4), (6, 4), (5, 5), (10, 3), (15, 2), (1, 6)]


def mat_mul(x: Mat2, y: Mat2) -> Mat2:
    (a, b), (c, d) = x
    (e, f), (g, h) = y
    return ((a * e + b * g, a * f + b * h), (c * e + d * g, c * f + d * h))


def al_matrix(n: int, e: int) -> Mat2:
    """The fixed W_e (independent of both implementations)."""
    if e == 1:
        return ((1, 0), (0, 1))
    f = n // e
    w = next(w for w in range(1, f + 1) if (e * w - 1) % f == 0)
    return ((e, (e * w - 1) // f), (n, e * w))


def divisors(n: int) -> list[int]:
    return [d for d in range(1, n + 1) if n % d == 0]


def random_gamma0_star(rnd: random.Random, n: int, steps: int = 6) -> Mat2:
    """A random integral matrix in Gamma_0(N)^* (a word in generators and the W_e)."""
    gens: list[Mat2] = [
        ((1, 1), (0, 1)),
        ((1, -1), (0, 1)),
        ((1, 0), (n, 1)),
        ((1, 0), (-n, 1)),
        ((-1, 0), (0, -1)),
    ]
    gens += [al_matrix(n, e) for e in divisors(n) if n % e == 0 and _coprime(e, n // e)]
    g: Mat2 = ((1, 0), (0, 1))
    for _ in range(rnd.randrange(0, steps)):
        g = mat_mul(g, rnd.choice(gens))
    return g


def _coprime(a: int, b: int) -> bool:
    while b:
        a, b = b, a % b
    return a == 1


def outcome(f: Callable[[], object]) -> tuple[str, object]:
    """("ok", value) or ("error", exception class), for comparing implementations."""
    try:
        return ("ok", f())
    except Exception as exc:
        return ("error", type(exc))
