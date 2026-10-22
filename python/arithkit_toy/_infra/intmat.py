"""Integer 2x2 matrices as tuples ((a, b), (c, d)), for the toy implementation."""

from __future__ import annotations

type Mat2 = tuple[tuple[int, int], tuple[int, int]]


def mul(x: Mat2, y: Mat2) -> Mat2:
    """The matrix product x y."""
    (a, b), (c, d) = x
    (e, f), (g, h) = y
    return ((a * e + b * g, a * f + b * h), (c * e + d * g, c * f + d * h))


def adj(x: Mat2) -> Mat2:
    """The adjugate: x adj(x) = det(x) 1."""
    (a, b), (c, d) = x
    return ((d, -b), (-c, a))


def det(x: Mat2) -> int:
    """The determinant."""
    (a, b), (c, d) = x
    return a * d - b * c


def divide_exactly(x: Mat2, q: int) -> Mat2:
    """x / q; raises ArithmeticError unless q divides every entry."""
    (a, b), (c, d) = x
    if any(entry % q != 0 for entry in (a, b, c, d)):
        raise ArithmeticError("division is not exact")
    return ((a // q, b // q), (c // q, d // q))
