"""Toy implementation of :mod:`arithkit_api.modular.quotient`.

An element is a pair (e, u) standing for u W_e, see the module docstring of
:mod:`arithkit_api.modular.quotient`. All computations go through honest
integer 2x2 matrices: to apply phi_e or kappa we lift to integer matrices,
multiply, divide exactly and reduce modulo M again.
"""

from __future__ import annotations

import math
import operator
from collections.abc import Iterable
from itertools import product
from typing import Self, override

from arithkit_api import _json
from arithkit_api.errors import InvalidParameterError, NotInGroupError, ParentMismatchError
from arithkit_api.modular import quotient as api
from arithkit_api.modular import subgroup as api_subgroup
from arithkit_toy._infra import arith, intmat
from arithkit_toy._infra.intmat import Mat2

type Coords = tuple[int, int, int, int]

_BOUND = 2**63


def _type_product(e: int, f: int) -> int:
    """The product e * f = ef/gcd(e, f)^2 in the type group T_N (def:type)."""
    g = math.gcd(e, f)
    return e * f // (g * g)


def _al_matrix(n: int, e: int) -> Mat2:
    """The fixed Atkin--Lehner matrix W_e for the Hall divisor e of n (proof of lem:global-al)."""
    if e == 1:
        return ((1, 0), (0, 1))
    f = n // e
    w = 1
    while (e * w) % f != 1 % f:
        w += 1
    y = (e * w - 1) // f
    return ((e, y), (n, e * w))


def _as_tuple_of_four(u: object) -> Coords:
    if not isinstance(u, tuple) or len(u) != 4:  # pyright: ignore[reportUnknownArgumentType]
        raise TypeError("u must be a tuple of four integers")
    a, b, c, d = (operator.index(x) for x in u)  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
    return a, b, c, d


class _QuotientGroup:
    """Shared implementation of the adelic and the lifted quotient."""

    _lifted: bool = False
    _kind: str = ""

    def __init__(self, N: int, M: int) -> None:  # noqa: N803
        n, m = operator.index(N), operator.index(M)
        if not (1 <= n < _BOUND and 1 <= m < _BOUND):
            raise InvalidParameterError("need 1 <= N, M < 2^63")
        primes = arith.factor(n)
        if any(k > 1 for k in primes.values()):
            raise InvalidParameterError("N must be squarefree")
        self._n = n
        self._m = m
        self._primes = tuple(primes)
        self._divisors = tuple(
            sorted(
                math.prod(p for p, used in zip(self._primes, choice, strict=True) if used)
                for choice in product((False, True), repeat=len(self._primes))
            )
        )
        self._al = {e: _al_matrix(n, e) for e in self._divisors}

    # -- parameters ---------------------------------------------------------

    @property
    def N(self) -> int:  # noqa: N802
        return self._n

    @property
    def M(self) -> int:  # noqa: N802
        return self._m

    def type_group(self) -> tuple[int, ...]:
        return self._divisors

    # -- encoding helpers -----------------------------------------------------

    def _lift(self, u: Coords) -> Mat2:
        """The integer matrix ((a, b), (Nc, d)) lifting the coordinates u."""
        a, b, c, d = u
        return ((a, b), (self._n * c, d))

    def _coords(self, x: Mat2) -> Coords:
        """The coordinates modulo M of an integer matrix x in R_0(N)."""
        (a, b), (nc, d) = x
        if nc % self._n != 0:
            raise ArithmeticError("matrix is not in R_0(N)")
        m = self._m
        return (a % m, b % m, (nc // self._n) % m, d % m)

    def _twisted_mul(self, u: Coords, v: Coords) -> Coords:
        """The product in R_0(N)/M R_0(N) (prop:eichler-model)."""
        return self._coords(intmat.mul(self._lift(u), self._lift(v)))

    def _det(self, u: Coords) -> int:
        a, b, c, d = u
        return (a * d - self._n * b * c) % self._m

    def _is_valid_det(self, u: Coords) -> bool:
        if self._lifted:
            return self._det(u) == 1 % self._m
        return arith.is_unit_mod(self._det(u), self._m)

    def _phi(self, e: int, u: Coords) -> Coords:
        """phi_e(u) = W_e u W_e^{-1} = W_e u adj(W_e) / e (prop:al-encoding (1))."""
        w = self._al[e]
        y = intmat.mul(intmat.mul(w, self._lift(u)), intmat.adj(w))
        return self._coords(intmat.divide_exactly(y, e))

    def _phi_inverse(self, e: int, u: Coords) -> Coords:
        """phi_e^{-1}(u) = W_e^{-1} u W_e = adj(W_e) u W_e / e."""
        w = self._al[e]
        y = intmat.mul(intmat.mul(intmat.adj(w), self._lift(u)), w)
        return self._coords(intmat.divide_exactly(y, e))

    def _kappa(self, e: int, f: int) -> Coords:
        """kappa(e, f) = gcd(e, f)^{-1} W_e W_f W_{e*f}^{-1}, in Gamma_0(N) (prop:al-encoding (2))."""
        ef = _type_product(e, f)
        k = intmat.mul(intmat.mul(self._al[e], self._al[f]), intmat.adj(self._al[ef]))
        k = intmat.divide_exactly(k, math.gcd(e, f) * ef)
        if intmat.det(k) != 1:
            raise ArithmeticError("kappa does not have determinant 1")
        return self._coords(k)

    def _unit_inverse(self, u: Coords) -> Coords:
        """The inverse of u in (R_0(N)/M R_0(N))^x: det^{-1} (d, -b, -c, a)."""
        a, b, c, d = u
        t = arith.inverse_mod(self._det(u), self._m)
        m = self._m
        return (t * d % m, -t * b % m, -t * c % m, t * a % m)

    # -- group law --------------------------------------------------------------

    def _make(self, e: int, u: Coords) -> QuotientElement:
        return QuotientElement(self, e, u)

    def _multiply(self, x: QuotientElement, y: QuotientElement) -> QuotientElement:
        """(e, u)(f, v) = (e * f, u phi_e(v) kappa(e, f)) (prop:al-encoding (3))."""
        u = self._twisted_mul(x.u, self._phi(x.e, y.u))
        u = self._twisted_mul(u, self._kappa(x.e, y.e))
        return self._make(_type_product(x.e, y.e), u)

    def _invert(self, x: QuotientElement) -> QuotientElement:
        """The inverse (e, v) of (e, u): phi_e(v) = u^{-1} kappa(e, e)^{-1}, since e * e = 1."""
        target = self._twisted_mul(self._unit_inverse(x.u), self._unit_inverse(self._kappa(x.e, x.e)))
        return self._make(x.e, self._phi_inverse(x.e, target))

    # -- public interface --------------------------------------------------------

    def _check_type(self, e: int) -> int:
        e = operator.index(e)
        if e < 1 or self._n % e != 0:
            raise NotInGroupError(f"{e} is not a positive divisor of N = {self._n}")
        return e

    def __call__(self, e: int, u: tuple[int, int, int, int]) -> QuotientElement:
        e = self._check_type(e)
        m = self._m
        a, b, c, d = _as_tuple_of_four(u)
        coords = (a % m, b % m, c % m, d % m)
        if not self._is_valid_det(coords):
            raise NotInGroupError("det u is not a unit" if not self._lifted else "det u is not 1")
        return self._make(e, coords)

    def identity(self) -> QuotientElement:
        return self._make(1, (1 % self._m, 0, 0, 1 % self._m))

    def al_element(self, e: int) -> QuotientElement:
        e = self._check_type(e)
        return self._make(e, (1 % self._m, 0, 0, 1 % self._m))

    def _unit_group_order(self) -> int:
        """|(R_0(N)/M R_0(N))^x|, multiplicative over the prime powers p^k exactly dividing M.

        For p not dividing N the factor is |GL_2(Z/p^k)| = p^(4k-4) (p^2-1)(p^2-p);
        for p dividing N it is p^(4k) (1 - 1/p)^2, since an element of the Iwahori
        order is a unit iff its diagonal entries are units modulo p.
        """
        total = 1
        for p, k in arith.factor(self._m).items():
            if self._n % p == 0:
                total *= p ** (4 * k - 2) * (p - 1) ** 2
            else:
                total *= p ** (4 * k - 4) * (p * p - 1) * (p * p - p)
        return total

    def order(self) -> int:
        size = len(self._divisors) * self._unit_group_order()
        if self._lifted:
            size //= arith.euler_phi(self._m)
        return size

    def elements(self) -> tuple[QuotientElement, ...]:
        m = self._m
        return tuple(
            self._make(e, (a, b, c, d))
            for e in self._divisors
            for a, b, c, d in product(range(m), repeat=4)
            if self._is_valid_det((a, b, c, d))
        )

    def subgroup(self, gens: Iterable[api.QuotientElement]) -> api_subgroup.QuotientSubgroup:
        from arithkit_toy.modular.subgroup import QuotientSubgroup

        return QuotientSubgroup(self, [self._own(g) for g in gens])

    def _own(self, x: object) -> QuotientElement:
        """x as an element of this group; TypeError / ParentMismatchError otherwise."""
        if not isinstance(x, QuotientElement):
            raise TypeError(f"expected a toy QuotientElement, not {type(x).__name__}")
        if x.parent() != self:
            raise ParentMismatchError("element of a different parent")
        return x

    def _json_value(self) -> dict[str, object]:
        return _json.encode_quotient(self._kind, self._n, self._m)

    def element_from_json(self, text: str) -> QuotientElement:
        e, u = _json.decode_element(_json.loads(text), self._n, self._m)
        if not self._is_valid_det(u):
            raise NotInGroupError("determinant condition fails")
        return self._make(e, u)

    def to_json(self) -> str:
        return _json.dumps(self._json_value())

    @override
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, _QuotientGroup):
            return NotImplemented
        return (self._lifted, self._n, self._m) == (other._lifted, other._n, other._m)

    @override
    def __hash__(self) -> int:
        return hash((self._lifted, self._n, self._m))

    @override
    def __repr__(self) -> str:
        return f"{self._kind}({self._n}, {self._m})"


class AdelicQuotient(_QuotientGroup, api.AdelicQuotient):
    """Toy implementation of :class:`arithkit_api.modular.quotient.AdelicQuotient`."""

    _lifted = False
    _kind = "AdelicQuotient"

    def to_lifted(self, x: api.QuotientElement) -> api.QuotientElement:
        x = self._own(x)
        if self._det(x.u) != 1 % self._m:
            raise NotInGroupError("det u is not 1")
        return LiftedQuotient(self._n, self._m)._make(x.e, x.u)


class LiftedQuotient(_QuotientGroup, api.LiftedQuotient):
    """Toy implementation of :class:`arithkit_api.modular.quotient.LiftedQuotient`."""

    _lifted = True
    _kind = "LiftedQuotient"

    def from_matrix(self, g: tuple[tuple[int, int], tuple[int, int]]) -> api.QuotientElement:
        """See :meth:`arithkit_api.modular.quotient.LiftedQuotient.from_matrix`.

        Write g = q gamma W_e. Then g adj(W_e) = q e gamma, so with
        D = det g = q^2 e we get s := q e = sqrt(D e) and gamma = g adj(W_e) / s.
        """
        x = _as_matrix(g)
        big_d = intmat.det(x)
        if big_d <= 0:
            raise NotInGroupError("the determinant must be positive")
        e = math.prod(p for p in self._primes if arith.valuation(big_d, p) % 2 == 1)
        s = math.isqrt(big_d * e)
        if s * s != big_d * e:
            raise NotInGroupError("not in Gamma_0(N)^* modulo Q_{>0}")
        try:
            gamma = intmat.divide_exactly(intmat.mul(x, intmat.adj(self._al[e])), s)
            u = self._coords(gamma)
        except ArithmeticError:
            raise NotInGroupError("not in Gamma_0(N)^* modulo Q_{>0}") from None
        return self._make(e, u)

    def to_adelic(self, x: api.QuotientElement) -> api.QuotientElement:
        x = self._own(x)
        return AdelicQuotient(self._n, self._m)._make(x.e, x.u)


def _as_matrix(g: object) -> Mat2:
    if not isinstance(g, tuple) or len(g) != 2:  # pyright: ignore[reportUnknownArgumentType]
        raise TypeError("g must be a tuple of two tuples of two integers")
    rows: list[tuple[int, int]] = []
    for row in g:  # pyright: ignore[reportUnknownVariableType]
        if not isinstance(row, tuple) or len(row) != 2:  # pyright: ignore[reportUnknownArgumentType]
            raise TypeError("g must be a tuple of two tuples of two integers")
        rows.append((operator.index(row[0]), operator.index(row[1])))  # pyright: ignore[reportUnknownArgumentType]
    return (rows[0], rows[1])


class QuotientElement(api.QuotientElement):
    """Toy implementation of :class:`arithkit_api.modular.quotient.QuotientElement`."""

    __slots__ = ("_parent", "e", "u")

    def __init__(self, parent: _QuotientGroup, e: int, u: Coords) -> None:
        self._parent = parent
        self.e = e
        self.u = u

    def parent(self) -> api.AdelicQuotient | api.LiftedQuotient:
        assert isinstance(self._parent, AdelicQuotient | LiftedQuotient)
        return self._parent

    def coordinates(self) -> tuple[int, tuple[int, int, int, int]]:
        return (self.e, self.u)

    def type(self) -> int:
        return self.e

    def det(self) -> int:
        return self._parent._det(self.u)  # pyright: ignore[reportPrivateUsage]

    def order(self) -> int:
        identity = self._parent.identity()
        power, k = self, 1
        while power != identity:
            power, k = power * self, k + 1
        return k

    def inverse(self) -> Self:
        result = self._parent._invert(self)  # pyright: ignore[reportPrivateUsage]
        assert isinstance(result, type(self))
        return result

    def _same_parent(self, other: object) -> QuotientElement | None:
        if not isinstance(other, QuotientElement):
            return None
        if other._parent != self._parent:
            raise ParentMismatchError("elements of different parents")
        return other

    def __mul__(self, other: Self) -> Self:
        y = self._same_parent(other)
        if y is None:
            return NotImplemented
        result = self._parent._multiply(self, y)  # pyright: ignore[reportPrivateUsage]
        assert isinstance(result, type(self))
        return result

    def __pow__(self, k: int) -> Self:
        k = operator.index(k)
        base = self if k >= 0 else self.inverse()
        k = abs(k)
        result = self._parent.identity()
        while k > 0:
            if k % 2 == 1:
                result = result * base
            base = base * base
            k //= 2
        assert isinstance(result, type(self))
        return result

    @override
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, QuotientElement):
            return NotImplemented
        return self._parent == other._parent and (self.e, self.u) == (other.e, other.u)

    @override
    def __hash__(self) -> int:
        return hash((self._parent, self.e, self.u))

    @override
    def __repr__(self) -> str:
        return f"({self.e}, {self.u}) in {self._parent!r}"

    def to_json(self) -> str:
        return _json.dumps(_json.encode_element(self.e, self.u))

    def to_json_full(self) -> str:
        return _json.dumps(
            {"parent": self._parent._json_value(), "element": _json.encode_element(self.e, self.u)}  # pyright: ignore[reportPrivateUsage]
        )


def quotient_from_json(text: str) -> api.AdelicQuotient | api.LiftedQuotient:
    """See :func:`arithkit_api.modular.quotient.quotient_from_json`."""
    return _quotient_from_value(_json.loads(text))


def _quotient_from_value(value: object) -> AdelicQuotient | LiftedQuotient:
    kind, n, m = _json.decode_quotient(value)
    return AdelicQuotient(n, m) if kind == "AdelicQuotient" else LiftedQuotient(n, m)
