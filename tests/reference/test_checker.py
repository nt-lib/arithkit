"""The reference data checker on small synthetic trees."""

from __future__ import annotations

import json
import pathlib
import shutil

import pytest
from tools.reference import model

pytestmark = pytest.mark.toy

REAL_ROOT = pathlib.Path(__file__).resolve().parents[2] / "reference"


def dumps(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def make_tree(tmp: pathlib.Path) -> pathlib.Path:
    root = tmp / "reference"
    (root / "quantities").mkdir(parents=True)
    (root / "recipes" / "arithkit_toy").mkdir(parents=True)
    (root / "recipes" / "magma").mkdir(parents=True)
    (root / "data" / "sq").mkdir(parents=True)
    (root / "retracted").mkdir()
    (root / "provenance").mkdir()
    (root / "assumptions.toml").write_text('[GRH]\ndescription = "GRH"\n')
    (root / "systems.toml").write_text("[arithkit_toy]\nin_repository = true\n[magma]\n")
    (root / "quantities" / "sq.toml").write_text(
        'name = "sq"\nkey = ["n"]\noutput = "int"\n[input]\nn = "int"\n'
    )
    (root / "recipes" / "arithkit_toy" / "sq.v1.toml").write_text(
        'id = "arithkit_toy.sq.v1"\nquantity = "sq"\nsystem = "arithkit_toy"\ntemplate = "n * n"\n'
        'parser = "int"\nassumes = []\n'
    )
    (root / "recipes" / "magma" / "sq.v1.toml").write_text(
        'id = "magma.sq.v1"\nquantity = "sq"\nsystem = "magma"\ntemplate = "{n}^2"\nparser = "int"\n'
        'assumes = ["GRH"]\n'
    )
    return root


def write_shard(root: pathlib.Path, shard_id: str, rows: dict[int, int], folder: str = "data") -> str:
    path = root / folder / shard_id
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [dumps({"format": 1, "quantity": "sq"})] + [dumps({"n": n, "out": v}) for n, v in rows.items()]
    path.write_text("\n".join(lines) + "\n")
    return model.sha256(path)


def event(root: pathlib.Path, **fields: object) -> None:
    fields.setdefault("date", "2026-10-23")
    fields.setdefault("host", "test")
    fields.setdefault("tool_commit", "0" * 40)
    with (root / "provenance" / "sq.jsonl").open("a") as f:
        f.write(dumps(fields) + "\n")


def support(root: pathlib.Path, kind: str, shard: str, digest: str, recipe: str) -> None:
    system = recipe.split(".")[0]
    event(
        root,
        event=kind,
        shard=shard,
        sha256=digest,
        recipe=recipe,
        recipe_sha256=model.sha256(model.load(root).recipe_paths[recipe]),
        system=system,
        system_version="ab" * 20 if system == "arithkit_toy" else "2.29",
        assumes=["GRH"] if system == "magma" else [],
    )


def retire(root: pathlib.Path, recipe: str, reason: str) -> None:
    system, name = recipe.split(".", 1)
    (root / "recipes-retired" / system).mkdir(parents=True, exist_ok=True)
    shutil.move(
        root / "recipes" / system / f"{name}.toml", root / "recipes-retired" / system / f"{name}.toml"
    )
    event(root, event="recipe_retired", recipe=recipe, reason=reason, explanation="test")


def check(root: pathlib.Path) -> list[str]:
    return model.check(model.load(root))


def test_real_reference_tree_is_consistent() -> None:
    assert check(REAL_ROOT) == []


def test_conditional_then_unconditional(tmp_path: pathlib.Path) -> None:
    root = make_tree(tmp_path)
    digest = write_shard(root, "sq/0001.jsonl", {1: 1, 2: 4, 3: 9})
    support(root, "produced", "sq/0001.jsonl", digest, "magma.sq.v1")
    assert check(root) == []
    assert model.status(model.load(root)) == {"sq/0001.jsonl": "conditional on GRH"}
    support(root, "confirmed", "sq/0001.jsonl", digest, "arithkit_toy.sq.v1")
    assert model.status(model.load(root)) == {"sq/0001.jsonl": "unconditional"}


def test_retired_recipes(tmp_path: pathlib.Path) -> None:
    root = make_tree(tmp_path)
    digest = write_shard(root, "sq/0001.jsonl", {1: 1, 2: 4})
    support(root, "produced", "sq/0001.jsonl", digest, "magma.sq.v1")
    support(root, "confirmed", "sq/0001.jsonl", digest, "arithkit_toy.sq.v1")
    # Moved without an event: inconsistent.
    shutil.move(root / "recipes" / "magma" / "sq.v1.toml", root / "sq.v1.toml")
    (root / "recipes-retired" / "magma").mkdir(parents=True)
    shutil.move(root / "sq.v1.toml", root / "recipes-retired" / "magma" / "sq.v1.toml")
    assert any("without a recipe_retired event" in p for p in check(root))
    event(root, event="recipe_retired", recipe="magma.sq.v1", reason="outdated", explanation="old")
    assert check(root) == []
    assert model.status(model.load(root)) == {"sq/0001.jsonl": "unconditional"}
    # A recipe retired for a bug no longer supports anything.
    retire(root, "arithkit_toy.sq.v1", "bug")
    assert check(root) == []
    assert model.status(model.load(root)) == {"sq/0001.jsonl": "conditional on GRH"}


def test_reproductions_need_system_and_commit(tmp_path: pathlib.Path) -> None:
    root = make_tree(tmp_path)
    digest = write_shard(root, "sq/0001.jsonl", {2: 4})
    recipe_sha = model.sha256(root / "recipes" / "arithkit_toy" / "sq.v1.toml")
    common = {"shard": "sq/0001.jsonl", "sha256": digest, "recipe": "arithkit_toy.sq.v1", "assumes": []}
    event(root, event="produced", recipe_sha256=recipe_sha, system="magma", system_version="x", **common)
    event(
        root,
        event="confirmed",
        recipe_sha256=recipe_sha,
        system="arithkit_toy",
        system_version="0.1.0",
        **common,
    )
    problems = check(root)
    assert any("system must be the recipe's system" in p for p in problems)
    assert any("commit hash" in p for p in problems)


def test_detects_tampering_and_unsupported_shards(tmp_path: pathlib.Path) -> None:
    root = make_tree(tmp_path)
    digest = write_shard(root, "sq/0001.jsonl", {1: 1, 2: 4})
    assert any("no produced" in p for p in check(root))
    support(root, "produced", "sq/0001.jsonl", digest, "arithkit_toy.sq.v1")
    assert check(root) == []
    with (root / "data" / "sq" / "0001.jsonl").open("a") as f:
        f.write(dumps({"n": 3, "out": 9}) + "\n")
    assert any("sha256 does not match" in p for p in check(root))


def test_recipes_are_immutable(tmp_path: pathlib.Path) -> None:
    root = make_tree(tmp_path)
    digest = write_shard(root, "sq/0001.jsonl", {2: 4})
    support(root, "produced", "sq/0001.jsonl", digest, "arithkit_toy.sq.v1")
    recipe = root / "recipes" / "arithkit_toy" / "sq.v1.toml"
    recipe.write_text(recipe.read_text().replace("n * n", "n ** 2"))
    assert any("has changed" in p for p in check(root))


def test_conflicts_between_active_shards(tmp_path: pathlib.Path) -> None:
    root = make_tree(tmp_path)
    d1 = write_shard(root, "sq/0001.jsonl", {2: 4})
    d2 = write_shard(root, "sq/0002.jsonl", {2: 5})
    support(root, "produced", "sq/0001.jsonl", d1, "arithkit_toy.sq.v1")
    support(root, "produced", "sq/0002.jsonl", d2, "arithkit_toy.sq.v1")
    assert any("conflicts" in p for p in check(root))


def test_retraction_and_inheritance(tmp_path: pathlib.Path) -> None:
    root = make_tree(tmp_path)
    bad = write_shard(root, "sq/0001.jsonl", {1: 1, 2: 5, 3: 9})
    support(root, "produced", "sq/0001.jsonl", bad, "arithkit_toy.sq.v1")
    assert check(root) == []
    # Retract: move the shard unchanged and record the event.
    (root / "retracted" / "sq").mkdir(parents=True)
    shutil.move(root / "data" / "sq" / "0001.jsonl", root / "retracted" / "sq" / "0001.jsonl")
    assert any("without a retracted event" in p for p in check(root))
    event(
        root,
        event="retracted",
        shard="sq/0001.jsonl",
        sha256=bad,
        reason="2^2 is 4",
        superseded_by="sq/0002.jsonl",
    )
    # The corrected shard keeps rows 1 and 3 verbatim and fixes row 2.
    good = write_shard(root, "sq/0002.jsonl", {1: 1, 2: 4, 3: 9})
    event(
        root,
        event="inherited",
        shard="sq/0002.jsonl",
        sha256=good,
        source="sq/0001.jsonl",
        source_sha256=bad,
        excluded=[[2]],
    )
    tree = model.load(root)
    assert model.check(tree) == []
    assert model.status(tree) == {"sq/0002.jsonl": "unsupported"}  # row 2 has no support yet
    support(root, "confirmed", "sq/0002.jsonl", good, "magma.sq.v1")
    assert model.status(model.load(root)) == {"sq/0002.jsonl": "conditional on GRH"}
    support(root, "confirmed", "sq/0002.jsonl", good, "arithkit_toy.sq.v1")
    assert model.status(model.load(root)) == {"sq/0002.jsonl": "unconditional"}


def test_inherited_rows_must_be_identical(tmp_path: pathlib.Path) -> None:
    root = make_tree(tmp_path)
    source = write_shard(root, "sq/0001.jsonl", {1: 1, 2: 4})
    support(root, "produced", "sq/0001.jsonl", source, "arithkit_toy.sq.v1")
    copy = write_shard(root, "sq/0002.jsonl", {1: 1, 2: 4, 5: 25})
    event(
        root,
        event="inherited",
        shard="sq/0002.jsonl",
        sha256=copy,
        source="sq/0001.jsonl",
        source_sha256=source,
        excluded=[],
    )
    assert check(root) == []
    tampered = root / "data" / "sq" / "0003.jsonl"
    tampered.write_text(dumps({"format": 1, "quantity": "sq"}) + "\n" + '{"n":2, "out":4}\n')
    event(
        root,
        event="inherited",
        shard="sq/0003.jsonl",
        sha256=model.sha256(tampered),
        source="sq/0001.jsonl",
        source_sha256=source,
        excluded=[],
    )
    assert any("differs from the source" in p for p in check(root))
