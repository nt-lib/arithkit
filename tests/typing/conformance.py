"""Checked by pyright only (not a test module): both implementations conform to the Protocols."""

from __future__ import annotations

from arithkit.modular import quotient as native_quotient
from arithkit.modular import subgroup as native_subgroup
from arithkit_api.modular import quotient as api_quotient
from arithkit_api.modular import subgroup as api_subgroup
from arithkit_toy.modular import quotient as toy_quotient
from arithkit_toy.modular import subgroup as toy_subgroup


def check_toy(x: toy_quotient.QuotientElement, h: toy_subgroup.QuotientSubgroup) -> None:
    _a: api_quotient.GL2ASubQuotient = toy_quotient.GL2ASubQuotient(6, 5)
    _l: api_quotient.GL2QSubQuotient = toy_quotient.GL2QSubQuotient(6, 5)
    _x: api_quotient.QuotientElement = x
    _h: api_subgroup.QuotientSubgroup = h


def check_native(x: native_quotient.QuotientElement, h: native_subgroup.QuotientSubgroup) -> None:
    _a: api_quotient.GL2ASubQuotient = native_quotient.GL2ASubQuotient(6, 5)
    _l: api_quotient.GL2QSubQuotient = native_quotient.GL2QSubQuotient(6, 5)
    _x: api_quotient.QuotientElement = x
    _h: api_subgroup.QuotientSubgroup = h
