"""The interface definition of arithkit.

This package contains no mathematics. It defines

* the abstract types (:class:`typing.Protocol` classes) that both the toy
  implementation (``arithkit_toy``) and the native implementation
  (``arithkit``) implement, together with their canonical docstrings;
* the exception classes raised by both implementations (:mod:`arithkit_api.errors`);
* the canonical JSON helpers shared by both implementations (:mod:`arithkit_api._json`);
* the markers for the determinacy level of outputs (:mod:`arithkit_api.levels`).

Mathematical references of the form ``prop:al-encoding`` are labels in the TeX
document ``maths/quotients/`` of this repository.
"""
