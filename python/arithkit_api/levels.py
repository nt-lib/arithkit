"""Determinacy levels of outputs.

Every output of an arithkit function has one of four levels. The level is
marked on the return annotation with :data:`typing.Annotated`; an unmarked
output is :class:`Canonical`.

1. :class:`Canonical`: independent of any choice. The toy and native
   implementations, and any other system computing the same thing, agree
   exactly.
2. :class:`Deterministic`: not canonical, but fixed by a specified, versioned
   deterministic algorithm. Toy and native agree exactly; other systems need
   not.
3. :class:`Characterised`: any value with a stated mathematical property is
   allowed (for instance a shortest vector). Both implementations' outputs
   pass the verification function; canonical invariants are compared exactly.
4. :class:`Random`: random on purpose, from an explicit seed. Both
   implementations use the same specified pseudorandom generator, so the same
   seed gives the same output everywhere.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Canonical:
    """Level 1: the output does not depend on any choice."""


@dataclass(frozen=True)
class Deterministic:
    """Level 2: the output of the named, versioned deterministic algorithm."""

    algorithm: str
    version: int


@dataclass(frozen=True)
class Characterised:
    """Level 3: any value satisfying the documented property; ``verify`` names the check."""

    verify: str


@dataclass(frozen=True)
class Random:
    """Level 4: random output determined by the ``seed`` argument."""

    seed_argument: str = "seed"
