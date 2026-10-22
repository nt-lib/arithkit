# CLAUDE.md

Guidance for working on arithkit. All conventions below are deliberate; do not "fix" them.

## What this is

Maintainable, correct, reasonably fast mathematics code. Priorities: correctness > maintainability >
performance. Every algorithm exists twice with an identical Python interface:

1. `python/arithkit_toy/` - toy implementation: pure Python, standard library only (no Sage, no sympy),
   written to be as easy to understand as possible. No speed tricks. It is the oracle.
2. `native/` - the Rust implementation (fast, but readable; no tricks that trade correctness for speed).
3. `python/arithkit/` - the Python interface to the Rust code: the PyO3 classes re-exported, plus
   hand-written `.pyi` stubs that are the typed contract.

`python/arithkit_api/` defines the interface: typing Protocols with the canonical docstrings, the
exception classes (`errors.py`), the shared canonical JSON helpers (`_json.py`) and the determinacy
level markers (`levels.py`). Any difference in behaviour between toy and native is a bug.

This repository does NOT use the nt-lib research template or the nt-lib-new-submodule skill; it was
set up by hand on purpose.

The mathematics lives in `maths/` (TeX). `maths/quotients/` is Maarten's document "Quotients of
modular curves: an adelic big picture"; code and docstrings cite its labels (e.g. `prop:al-encoding`).
`maths/quotients/sections/algorithms.tex` documents the conventions and algorithms implemented here.

## Layout and mirroring rule

```
python/arithkit_api/modular/{quotient,subgroup}.py   Protocols
python/arithkit_toy/modular/{quotient,subgroup}.py   toy
python/arithkit/modular/{quotient,subgroup}.py/.pyi  native re-exports + stubs
native/core/src/modular/{quotient,subgroup}.rs       Rust maths (crate arithkit-core, no PyO3)
native/py/src/modular/{quotient,subgroup}.rs         PyO3 bindings (crate arithkit-py -> arithkit._native)
native/bigint/                                       BigInt newtype (crate arithkit-bigint)
tests/{spec,agreement,structure,typing}/
reference/, tools/reference/, crosscheck/{sage,magma,pari}/
docs/ (Sphinx, from arithkit_api only)
```

- The mathematical tree (`modular/...`) is identical in all five places; `foo.py` <-> `foo.rs`;
  identical snake_case function names. Python class `Foo` <-> core `struct Foo` <-> binding
  `struct PyFoo` with `#[pyclass(name = "Foo")]` (the `Py` prefix is the only transformation).
- Not mirrored: `arithkit_api/{errors,_json,levels}.py`, `arithkit_toy/_infra/`, `native/core/src/infra/`,
  `native/py/src/convert.rs`, the bigint crate.
- Toy and stubs have no public names beyond the Protocols (helpers are `_private`). The structure test
  (`tests/structure/`) enforces names, parameters and annotations (module qualifiers are ignored).
- Public annotations use only arithkit_api types, `Self` and builtins.

## Semantics rules

- Same exception class under exactly the same conditions in both implementations (messages may
  differ). Classes come from `arithkit_api.errors`; wrong Python argument types raise `TypeError`.
- Rust: user-reachable failures return `infra::errors::Result`, mapped to Python in `convert.rs`.
  A panic is always a bug. `unsafe` is forbidden in every crate. `overflow-checks = true` in release.
- Objects are immutable and hashable; equality only within equal parents (never equal to plain
  Python values; hashes need not agree between implementations). No coercion; explicit conversions.
  Arithmetic between different parents of one implementation raises `ParentMismatchError`; toy and
  native objects never interact (`TypeError`).
- Determinacy levels (`arithkit_api.levels`), marked per output with `Annotated[...]`, unmarked =
  Canonical: Canonical (equal everywhere), Deterministic(algorithm, version) (equal toy vs native,
  algorithm specified and versioned), Characterised(verify) (any value with the stated property),
  Random(seed) (one shared specified PRNG, same seed -> same output in both implementations).
- Canonical JSON via `arithkit_api._json` only (sorted keys, no whitespace, no floats, ints with
  >= 4000 digits refused). Elements are encoded relative to their parent.
- Single-threaded forever; parallelism is by processes. Randomness takes explicit seeds.
- Long Rust loops call `infra::interrupt::Poll::tick()` (Cargo feature `interrupt`, default on;
  Ctrl-C -> `KeyboardInterrupt`). A single huge bigint operation cannot be interrupted.
- `N, M < 2^63`; residues are `u64` with `u128` products. BigInt (dashu, provisional - benchmark against
  GMP/FLINT before LMFDB-scale use) is only used for exact integer matrix work and conversions.

## Adding an algorithm

1. Write or cite the mathematics in `maths/` (conventions, canonical choices, proofs).
2. Add the Protocol with docstring to `arithkit_api` (mark non-canonical outputs).
3. Toy implementation, then spec tests in `tests/spec/` (they run against both implementations).
4. Rust in `native/core`, bindings in `native/py`, stub `.pyi`; agreement tests in `tests/agreement/`.
5. Bulk operations belong in Rust (per-call overhead from Python dominates for small objects).

## Commands

Local toolchain: conda env `arithkit` (rust, uv, maturin, tectonic). Prefix commands with
`conda run -n arithkit`.

```
uv sync                                   # build + install (editable; rebuilt when .rs files change)
uv run pytest                             # everything (slow tier excluded)
uv run pytest -m toy                      # toy only (with `uv sync --no-install-project`, no Rust needed)
HYPOTHESIS_PROFILE=nightly uv run pytest  # many random examples
cargo test --workspace --exclude arithkit-py
cargo clippy --workspace --all-targets -- -D warnings ; cargo fmt --all --check
uv run ruff check . ; uv run ruff format --check . ; uv run pyright
uv run sphinx-build -W docs docs/_build
uv run python -m tools.reference check    # reference data checker
cd maths/quotients && tectonic -X compile main.tex --outdir <tmpdir>
```

Never use `maturin develop` (one install route: uv). Temporary files go in `tmp/` (gitignored).

## Reference data (`reference/`)

- `quantities/*.toml`: what is computed (input schema, domain, output, canonical form).
- `recipes/<system>/*.toml`: immutable, versioned ways to compute a quantity in a system (toy, arithkit,
  sage, magma, pari, lmfdb), with `assumes` (names from `assumptions.toml`, e.g. GRH).
- `data/<quantity>/NNNN.jsonl`: immutable shards (<= 10 MB), first line a header; only believed-correct
  shards. Retraction = `git mv` to `retracted/` (same relative path) + a `retracted` event.
- `provenance/<quantity>.jsonl`: append-only events (produced, confirmed, disagreed, retracted,
  inherited) referring to shards by path and sha256. Status (unconditional / conditional) is derived,
  never stored. Never edit a shard or rewrite provenance; append instead.
- CAS code for comparisons lives only in `crosscheck/`; it is never part of the default test run.
- If the data approaches GitHub's repository limits, move it to an external database (not Git LFS).
