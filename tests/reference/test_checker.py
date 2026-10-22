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
    (root / "recipes" / "toy").mkdir(parents=True)
    (root / "recipes" / "magma").mkdir(parents=True)
    (root / "data" / "sq").mkdir(parents=True)
    (root / "retracted").mkdir()
    (root / "provenance").mkdir()
    (root / "assumptions.toml").write_text('[GRH]\ndescription = "GRH"\n')
    (root / "quantities" / "sq.toml").write_text(
        'name = "sq"\nkey = ["n"]\noutput = "int"\n[input]\nn = "int"\n'
    )
    (root / "recipes" / "toy" / "sq.v1.toml").write_text(
        'id = "toy.sq.v1"\nquantity = "sq"\nsystem = "toy"\ntemplate = "n * n"\n'
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
        recipe_sha256=model.sha256(root / "recipes" / system / "sq.v1.toml"),
        system_version="test",
        assumes=["GRH"] if system == "magma" else [],
    )


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
    support(root, "confirmed", "sq/0001.jsonl", digest, "toy.sq.v1")
    assert model.status(model.load(root)) == {"sq/0001.jsonl": "unconditional"}
    event(root, event="retracted_recipe", recipe="toy.sq.v1", reason="bug")
    assert model.status(model.load(root)) == {"sq/0001.jsonl": "conditional on GRH"}


def test_detects_tampering_and_unsupported_shards(tmp_path: pathlib.Path) -> None:
    root = make_tree(tmp_path)
    digest = write_shard(root, "sq/0001.jsonl", {1: 1, 2: 4})
    assert any("no produced" in p for p in check(root))
    support(root, "produced", "sq/0001.jsonl", digest, "toy.sq.v1")
    assert check(root) == []
    with (root / "data" / "sq" / "0001.jsonl").open("a") as f:
        f.write(dumps({"n": 3, "out": 9}) + "\n")
    assert any("sha256 does not match" in p for p in check(root))


def test_recipes_are_immutable(tmp_path: pathlib.Path) -> None:
    root = make_tree(tmp_path)
    digest = write_shard(root, "sq/0001.jsonl", {2: 4})
    support(root, "produced", "sq/0001.jsonl", digest, "toy.sq.v1")
    recipe = root / "recipes" / "toy" / "sq.v1.toml"
    recipe.write_text(recipe.read_text().replace("n * n", "n ** 2"))
    assert any("has changed" in p for p in check(root))


def test_conflicts_between_active_shards(tmp_path: pathlib.Path) -> None:
    root = make_tree(tmp_path)
    d1 = write_shard(root, "sq/0001.jsonl", {2: 4})
    d2 = write_shard(root, "sq/0002.jsonl", {2: 5})
    support(root, "produced", "sq/0001.jsonl", d1, "toy.sq.v1")
    support(root, "produced", "sq/0002.jsonl", d2, "toy.sq.v1")
    assert any("conflicts" in p for p in check(root))


def test_retraction_and_inheritance(tmp_path: pathlib.Path) -> None:
    root = make_tree(tmp_path)
    bad = write_shard(root, "sq/0001.jsonl", {1: 1, 2: 5, 3: 9})
    support(root, "produced", "sq/0001.jsonl", bad, "toy.sq.v1")
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
    support(root, "confirmed", "sq/0002.jsonl", good, "toy.sq.v1")
    assert model.status(model.load(root)) == {"sq/0002.jsonl": "unconditional"}


def test_inherited_rows_must_be_identical(tmp_path: pathlib.Path) -> None:
    root = make_tree(tmp_path)
    source = write_shard(root, "sq/0001.jsonl", {1: 1, 2: 4})
    support(root, "produced", "sq/0001.jsonl", source, "toy.sq.v1")
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
