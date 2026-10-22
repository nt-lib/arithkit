"""Sphinx configuration. The documentation is generated from arithkit_api only.

Docstrings write mathematics as $...$; a small hook turns that into :math:`...`.
"""

from __future__ import annotations

import pathlib
import re
import sys
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "python"))

project = "arithkit"
author = "Maarten Derickx"
copyright = "2026, Maarten Derickx"
extensions = ["sphinx.ext.autodoc", "sphinx.ext.mathjax"]
autodoc_member_order = "bysource"
autodoc_typehints = "signature"
autodoc_default_options = {"members": True, "special-members": "__call__, __mul__, __pow__, __contains__"}
html_theme = "alabaster"
exclude_patterns = ["_build"]
nitpicky = False

_MATH = re.compile(r"(?<![\\$])\$([^$]+)\$")


def _dollars_to_math(app: Any, what: str, name: str, obj: object, options: Any, lines: list[str]) -> None:
    text = "\n".join(lines)
    text = _MATH.sub(lambda m: f":math:`{m.group(1)}`", text)
    lines[:] = text.split("\n")


def setup(app: Any) -> None:
    app.connect("autodoc-process-docstring", _dollars_to_math)
