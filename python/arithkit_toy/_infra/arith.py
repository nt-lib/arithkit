"""Elementary number theory for the toy implementation."""

from __future__ import annotations

import math

# Miller--Rabin with these bases is deterministic for n < 3.3 * 10^24, which
# covers every n < 2^64 (Sorenson--Webster 2017).
_MR_BASES = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37)


def is_prime(n: int) -> bool:
    """Deterministic primality test for 0 <= n < 3.3 * 10^24."""
    if n < 2:
        return False
    for p in _MR_BASES:
        if n % p == 0:
            return n == p
    d, s = n - 1, 0
    while d % 2 == 0:
        d, s = d // 2, s + 1
    for a in _MR_BASES:
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(s - 1):
            x = x * x % n
            if x == n - 1:
                break
        else:
            return False
    return True


def _find_factor(n: int) -> int:
    """A nontrivial factor of the odd composite n (Pollard's rho, Floyd cycle finding)."""
    c = 1
    while True:
        x = y = 2
        d = 1
        while d == 1:
            x = (x * x + c) % n
            y = (y * y + c) % n
            y = (y * y + c) % n
            d = math.gcd(abs(x - y), n)
        if d != n:
            return d
        c += 1


def factor(n: int) -> dict[int, int]:
    """The factorisation of n >= 1 as {prime: exponent}."""
    result: dict[int, int] = {}
    for p in (2, 3, 5):
        while n % p == 0:
            result[p] = result.get(p, 0) + 1
            n //= p
    stack = [n] if n > 1 else []
    while stack:
        m = stack.pop()
        if is_prime(m):
            result[m] = result.get(m, 0) + 1
        else:
            d = _find_factor(m)
            stack.extend([d, m // d])
    return dict(sorted(result.items()))


def inverse_mod(a: int, m: int) -> int:
    """The inverse of a modulo m >= 1, in [0, m); ValueError if a is not a unit."""
    return pow(a, -1, m) if m > 1 else 0


def is_unit_mod(a: int, m: int) -> bool:
    """Whether a is a unit modulo m >= 1."""
    return math.gcd(a, m) == 1


def euler_phi(m: int) -> int:
    """Euler's totient of m >= 1."""
    result = m
    for p in factor(m):
        result = result // p * (p - 1)
    return result


def valuation(n: int, p: int) -> int:
    """The p-adic valuation of the nonzero integer n."""
    k = 0
    while n % p == 0:
        n //= p
        k += 1
    return k
