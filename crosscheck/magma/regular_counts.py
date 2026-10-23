"""Cross-check of subgroup_classes for N > 1 against Magma.

Magma cannot build the Atkin--Lehner quotients itself, so G is given by the regular permutation
representation computed from arithkit's group law (which is tested independently: from_matrix is a
homomorphism). Compares len(q.subgroup_classes(I)) with #Subgroups(G : IndexLimit := I).

Run from the repository root:  uv run python crosscheck/magma/regular_counts.py
"""

import subprocess

from arithkit.modular.quotient import GL2ASubQuotient as A
from arithkit.modular.quotient import GL2QSubQuotient as L

cases = [
    (A, 2, 3, 24),
    (L, 2, 3, 24),
    (A, 3, 4, 20),
    (L, 5, 2, 30),
    (A, 6, 5, 20),
    (L, 6, 5, 30),
    (A, 10, 3, 24),
    (A, 7, 2, 20),
    (L, 15, 4, 20),
    (A, 2, 4, 32),
]
lines = []
ours = []
for cls, n, m, bound in cases:
    q = cls(n, m)
    els = q.elements()
    pos = {x: i + 1 for i, x in enumerate(els)}
    gens = q.subgroup(els).gens()
    perms = ["[" + ",".join(str(pos[g * x]) for x in els) + "]" for g in gens]
    lines.append(f"G := sub<Sym({len(els)}) | {', '.join(perms)}>;")
    lines.append(f'printf "COUNT %o\\n", #Subgroups(G : IndexLimit := {bound});')
    ours.append((cls.__name__, n, m, bound, q.order(), len(q.subgroup_classes(bound))))
lines.append("quit;")
open("tmp/regular_counts.m", "w").write("\n".join(lines) + "\n")
out = subprocess.run(
    ["magma", "-n", "tmp/regular_counts.m"], stdin=subprocess.DEVNULL, capture_output=True, text=True
).stdout
counts = [int(line.split()[1]) for line in out.splitlines() if line.startswith("COUNT ")]
for (name, n, m, bound, order, c), mc in zip(ours, counts, strict=True):
    print(name, n, m, bound, "order", order, "ours", c, "magma", mc, "OK" if c == mc else "MISMATCH")
