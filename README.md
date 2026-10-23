# arithkit

> **Alpha.** arithkit is in alpha. Backward incompatible changes will be made, without deprecations or
> compatibility aliases, and development happens on `main` until the first release. Until then
> everything under `reference/` may be changed freely: old recipes and old shards may simply be removed.
> On the first release all generated data, including the provenance log, will be regenerated with the
> stable interface, and every recipe will then have exactly one version per implementation.

Arithmetic algorithms implemented twice, with exactly the same Python interface:

- `arithkit_toy`: a readable pure Python implementation (standard library only), the oracle;
- `arithkit`: a fast implementation in Rust (PyO3), the one to use.

The interface, with all docstrings, is defined in `arithkit_api` (typing Protocols). Any difference
in behaviour between the two implementations is a bug; the test suite compares them.

The principles of the project are summarised in [ZEN.md](ZEN.md).

Current content: the finite quotients Gamma_0(N)^* / Gamma(N;M) (adelic and lifted, fine version),
their elements and subgroups. The mathematics is in the TeX document `maths/quotients/`.

```python
from arithkit.modular.quotient import GL2QSubQuotient

q = GL2QSubQuotient(6, 5)
w = q.from_matrix(((0, -1), (6, 0)))
h = q.subgroup([w, q.al_element(2)])
print(h.order(), h.al_image(), h.to_json())
```

## Building and testing

Linux only. Requires Rust, [uv](https://docs.astral.sh/uv/) and maturin; locally they live in the
conda environment `arithkit` (`conda create -n arithkit -c conda-forge rust uv maturin tectonic`).

```sh
uv sync                      # builds the Rust extension (rebuilt automatically when sources change)
uv run pytest                # all tests: spec (both implementations), agreement, structure
uv run pytest -m toy         # toy only; works without Rust after `uv sync --no-install-project`
cargo test --workspace --exclude arithkit-py
uv run sphinx-build -W docs docs/_build
```

## Licence

MIT OR Apache-2.0, at your option.
