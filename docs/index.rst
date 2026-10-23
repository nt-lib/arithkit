arithkit
========

arithkit implements arithmetic algorithms twice: a readable pure Python toy
implementation (the oracle used in testing) and a fast Rust implementation,
exposed to Python with exactly the same interface. This documentation is
generated from :mod:`arithkit_api`, which defines that interface; use the
classes from :mod:`arithkit`.

.. code-block:: python

   from arithkit.modular.quotient import LiftedQuotient

   q = LiftedQuotient(6, 5)          # Gamma_0(6)^* / Gamma(6; 5), -1 kept
   w = q.from_matrix(((0, -1), (6, 0)))
   h = q.subgroup([w, q.al_element(2)])
   h.order(), h.al_image()

The mathematics is described in the TeX document ``maths/quotients/`` of the
repository (`compiled PDF <quotients.pdf>`_, including the section on the
conventions and algorithms of the implementation); docstrings refer to its
labels (e.g. ``prop:al-encoding``).

.. toctree::
   :maxdepth: 2

   api
