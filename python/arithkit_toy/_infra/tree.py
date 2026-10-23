"""The Bruhat--Tits tree of PGL_2(Q_p) in vertex coordinates (maths: def:vertex-coordinates).

A vertex is a triple (m, r, s): the class of the column span of [[p^m, b], [0, 1]] with
b = r / p^s, 0 <= b < p^m, and s = 0 or p not dividing r. Everything is done with integers.
"""

from __future__ import annotations

from collections import deque

from arithkit_toy._infra import intmat
from arithkit_toy._infra.arith import valuation
from arithkit_toy._infra.intmat import Mat2

type Vertex = tuple[int, int, int]

ORIGIN: Vertex = (0, 0, 0)


def standard_neighbour() -> Vertex:
    """o(p)_p = (-1, 0), the other end of the standard edge (the line F_p e_1)."""
    return (-1, 0, 0)


def normalise(p: int, m: int, numerator: int, s: int) -> Vertex:
    """The vertex (m, b) for b = numerator / p^s, with b reduced modulo p^m into [0, p^m)."""
    t = max(s, -m, 0)
    big = numerator * p ** (t - s)  # b = big / p^t
    big %= p ** (m + t)  # p^m = p^(m+t) / p^t
    while t > 0 and big % p == 0:
        big //= p
        t -= 1
    if big == 0:
        t = 0
    return (m, big, t)


def neighbours(p: int, v: Vertex) -> list[Vertex]:
    """The p + 1 neighbours (maths: lem:neighbours)."""
    m, r, s = v
    t = max(s, -m, 0)
    big = r * p ** (t - s)
    children = [normalise(p, m + 1, big + j * p ** (m + t), t) for j in range(p)]
    return [*children, normalise(p, m - 1, r, s)]


def basis(p: int, v: Vertex) -> tuple[Mat2, int]:
    """An integral matrix X = p^t [[p^m, b], [0, 1]] spanning a lattice of the class v, and t."""
    m, r, s = v
    t = max(s, -m, 0)
    return ((p ** (m + t), r * p ** (t - s)), (0, p**t)), t


def _val(x: int, p: int) -> float:
    return float("inf") if x == 0 else valuation(x, p)


def fixes(p: int, g: Mat2, v: Vertex) -> bool:
    """Whether the integral matrix g (nonzero determinant) fixes the vertex v (lem:fixed-vertex-test)."""
    d = intmat.det(g)
    k = valuation(d, p)
    if k % 2 == 1:
        return False
    x, _ = basis(p, v)
    y = intmat.mul(intmat.mul(intmat.adj(x), g), x)
    bound = valuation(intmat.det(x), p) + k // 2
    return all(_val(entry, p) >= bound for row in y for entry in row)


def ball(p: int, sources: list[Vertex], radius: int) -> list[Vertex]:
    """The vertices at distance <= radius from one of the sources, in breadth first order."""
    seen = set(sources)
    order = list(sources)
    queue = deque((v, 0) for v in sources)
    while queue:
        v, dist = queue.popleft()
        if dist == radius:
            continue
        for w in neighbours(p, v):
            if w not in seen:
                seen.add(w)
                order.append(w)
                queue.append((w, dist + 1))
    return order


def _farthest(p: int, vertices: set[Vertex], start: Vertex) -> tuple[Vertex, dict[Vertex, Vertex | None]]:
    """A vertex farthest from start inside the subtree, and the breadth first parents."""
    parent: dict[Vertex, Vertex | None] = {start: None}
    queue = deque([start])
    last = start
    while queue:
        v = queue.popleft()
        last = v
        for w in neighbours(p, v):
            if w in vertices and w not in parent:
                parent[w] = v
                queue.append(w)
    return last, parent


def centre(p: int, vertices: set[Vertex]) -> tuple[Vertex, Vertex]:
    """The centre of the (finite, nonempty) subtree spanned by the vertices (lem:centre).

    Returns (v, v) for a vertex and the two endpoints, in increasing order, for an edge midpoint.
    """
    a, _ = _farthest(p, vertices, min(vertices))
    b, parent = _farthest(p, vertices, a)
    path = [b]
    while (prev := parent[path[-1]]) is not None:
        path.append(prev)
    length = len(path) - 1
    if length % 2 == 0:
        mid = path[length // 2]
        return (mid, mid)
    x, y = path[length // 2], path[length // 2 + 1]
    return (min(x, y), max(x, y))
