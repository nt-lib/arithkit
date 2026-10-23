"""Loading, checking and deriving the status of a reference tree."""

from __future__ import annotations

import hashlib
import json
import pathlib
import tomllib
from dataclasses import dataclass, field

MAX_SHARD_BYTES = 10 * 1024 * 1024
SUPPORT_EVENTS = ("produced", "confirmed")
REPRODUCTION_EVENTS = ("produced", "confirmed", "disagreed")
EVENT_KINDS = (*REPRODUCTION_EVENTS, "retracted", "inherited", "recipe_retired")
RETIREMENT_REASONS = ("outdated", "bug")
RECIPE_FOLDERS = ("recipes", "recipes-retired")

type Key = tuple[object, ...]


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _as_list(value: object) -> list[object]:
    """A list-valued event field (missing means empty)."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("expected a list")
    return list(value)  # pyright: ignore[reportUnknownArgumentType]


def _freeze(value: object) -> object:
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)  # pyright: ignore[reportUnknownVariableType]
    return value


@dataclass
class Shard:
    """One shard file: its id (path relative to data/ or retracted/), rows by key, raw lines by key."""

    shard_id: str
    path: pathlib.Path
    active: bool
    quantity: str
    rows: dict[Key, object] = field(default_factory=lambda: {})
    lines: dict[Key, str] = field(default_factory=lambda: {})


@dataclass
class Tree:
    """A loaded reference tree."""

    root: pathlib.Path
    assumptions: set[str]
    quantities: dict[str, dict[str, object]]
    recipes: dict[str, dict[str, object]]
    recipe_paths: dict[str, pathlib.Path]
    retired: set[str]
    systems: dict[str, dict[str, object]]
    shards: dict[str, Shard]
    events: list[dict[str, object]]
    errors: list[str]


def _key_fields(quantity: dict[str, object]) -> list[str]:
    key = quantity.get("key")
    assert isinstance(key, list)
    return [str(k) for k in key]  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]


def load(root: pathlib.Path) -> Tree:
    """Load the tree; problems found while loading are collected in ``errors``."""
    errors: list[str] = []
    assumptions = set(tomllib.loads((root / "assumptions.toml").read_text()))
    quantities: dict[str, dict[str, object]] = {}
    for path in sorted((root / "quantities").glob("*.toml")):
        q = tomllib.loads(path.read_text())
        if q.get("name") != path.stem:
            errors.append(f"{path}: name must be {path.stem!r}")
        quantities[path.stem] = q
    systems: dict[str, dict[str, object]] = tomllib.loads((root / "systems.toml").read_text())
    recipes: dict[str, dict[str, object]] = {}
    recipe_paths: dict[str, pathlib.Path] = {}
    retired: set[str] = set()
    paths = [(folder, path) for folder in RECIPE_FOLDERS for path in sorted((root / folder).glob("*/*.toml"))]
    for folder, path in paths:
        r = tomllib.loads(path.read_text())
        rid = str(r.get("id"))
        expected = f"{path.parent.name}.{path.stem}"
        if rid != expected:
            errors.append(f"{path}: id must be {expected!r}")
        if r.get("system") != path.parent.name:
            errors.append(f"{path}: system must be {path.parent.name!r}")
        if path.parent.name not in systems:
            errors.append(f"{path}: system {path.parent.name!r} is not listed in systems.toml")
        if rid in recipes:
            errors.append(f"{path}: recipe id {rid} occurs twice")
        if folder == "recipes-retired":
            retired.add(rid)
        if r.get("quantity") not in quantities:
            errors.append(f"{path}: unknown quantity {r.get('quantity')!r}")
        assumes = r.get("assumes")
        if not isinstance(assumes, list) or not all(a in assumptions for a in assumes):  # pyright: ignore[reportUnknownVariableType]
            errors.append(f"{path}: assumes must be a list of names from assumptions.toml")
        recipes[rid] = r
        recipe_paths[rid] = path
    shards: dict[str, Shard] = {}
    for active, folder in ((True, "data"), (False, "retracted")):
        for path in sorted((root / folder).glob("*/*.jsonl")):
            shard_id = path.relative_to(root / folder).as_posix()
            if shard_id in shards:
                errors.append(f"shard {shard_id} exists in both data/ and retracted/")
                continue
            shards[shard_id] = _load_shard(shard_id, path, active, quantities, errors)
    events: list[dict[str, object]] = []
    for path in sorted((root / "provenance").glob("*.jsonl")):
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"{path}:{number}: invalid JSON ({exc})")
                continue
            if not isinstance(event, dict) or event.get("event") not in EVENT_KINDS:
                errors.append(f"{path}:{number}: unknown event")
                continue
            events.append(event)  # pyright: ignore[reportUnknownArgumentType]
    return Tree(
        root, assumptions, quantities, recipes, recipe_paths, retired, systems, shards, events, errors
    )


def _load_shard(
    shard_id: str,
    path: pathlib.Path,
    active: bool,
    quantities: dict[str, dict[str, object]],
    errors: list[str],
) -> Shard:
    lines = path.read_text().splitlines()
    quantity_name = path.parent.name
    shard = Shard(shard_id, path, active, quantity_name)
    if path.stat().st_size > MAX_SHARD_BYTES:
        errors.append(f"{shard_id}: larger than 10 MB")
    if not lines:
        errors.append(f"{shard_id}: empty shard")
        return shard
    header = json.loads(lines[0])
    if header != {"format": 1, "quantity": quantity_name}:
        errors.append(f'{shard_id}: header must be {{"format":1,"quantity":"{quantity_name}"}}')
    quantity = quantities.get(quantity_name)
    if quantity is None:
        errors.append(f"{shard_id}: unknown quantity {quantity_name!r}")
        return shard
    fields = _key_fields(quantity)
    for number, line in enumerate(lines[1:], start=2):
        row = json.loads(line)
        if not isinstance(row, dict) or set(row) != {*fields, "out"}:  # pyright: ignore[reportUnknownArgumentType]
            errors.append(f"{shard_id}:{number}: row must have exactly the fields {[*fields, 'out']}")
            continue
        key = tuple(_freeze(row[f]) for f in fields)
        if key in shard.rows:
            errors.append(f"{shard_id}:{number}: duplicate key {key}")
        shard.rows[key] = row["out"]
        shard.lines[key] = line
    return shard


def _event_shard(tree: Tree, event: dict[str, object], label: str) -> Shard | None:
    shard = tree.shards.get(str(event.get("shard")))
    if shard is None:
        tree.errors.append(f"{label}: unknown shard {event.get('shard')!r}")
        return None
    if event.get("sha256") != sha256(shard.path):
        tree.errors.append(f"{label}: sha256 does not match {shard.shard_id}")
    return shard


def check(tree: Tree) -> list[str]:
    """All problems of the tree (empty if it is consistent)."""
    retracted_ids: set[str] = set()
    supported: set[str] = set()
    retirements: set[str] = set()
    for number, event in enumerate(tree.events, start=1):
        label = f"event {number} ({event['event']})"
        kind = event["event"]
        if kind == "recipe_retired":
            recipe = str(event.get("recipe"))
            if recipe not in tree.retired:
                tree.errors.append(f"{label}: {recipe} is not in recipes-retired/")
            elif recipe in retirements:
                tree.errors.append(f"{label}: {recipe} retired twice")
            if event.get("reason") not in RETIREMENT_REASONS:
                tree.errors.append(f"{label}: reason must be one of {RETIREMENT_REASONS}")
            if not isinstance(event.get("explanation"), str) or not event.get("explanation"):
                tree.errors.append(f"{label}: an explanation is required")
            retirements.add(recipe)
            continue
        shard = _event_shard(tree, event, label)
        if shard is None:
            continue
        if kind in ("produced", "confirmed", "disagreed"):
            recipe = event.get("recipe")
            if recipe not in tree.recipes:
                tree.errors.append(f"{label}: unknown recipe {recipe!r}")
            elif event.get("recipe_sha256") != sha256(tree.recipe_paths[str(recipe)]):
                tree.errors.append(f"{label}: recipe {recipe} has changed (recipes are immutable)")
            elif tree.recipes[str(recipe)].get("quantity") != shard.quantity:
                tree.errors.append(f"{label}: recipe is for another quantity")
            elif event.get("system") != tree.recipes[str(recipe)].get("system"):
                tree.errors.append(f"{label}: system must be the recipe's system")
            version = event.get("system_version")
            if not isinstance(version, str) or not version:
                tree.errors.append(f"{label}: system_version is required")
            elif _in_repository(tree, str(event.get("system"))) and not _is_hex(version, 40):
                tree.errors.append(f"{label}: system_version must be a commit hash (40 hex digits)")
            if kind in SUPPORT_EVENTS:
                supported.add(shard.shard_id)
        elif kind == "retracted":
            retracted_ids.add(shard.shard_id)
        elif kind == "inherited":
            source = tree.shards.get(str(event.get("source")))
            if source is None or event.get("source_sha256") != sha256(source.path):
                tree.errors.append(f"{label}: unknown source or sha256 mismatch")
                continue
            excluded = {tuple(_freeze(k) for k in _as_list(key)) for key in _as_list(event.get("excluded"))}
            for key, line in shard.lines.items():
                if key in source.lines and key not in excluded and source.lines[key] != line:
                    tree.errors.append(f"{label}: row {key} differs from the source")
            supported.add(shard.shard_id)
    for recipe in sorted(tree.retired - retirements):
        tree.errors.append(f"{recipe}: in recipes-retired/ without a recipe_retired event")
    for shard in tree.shards.values():
        if shard.active and shard.shard_id in retracted_ids:
            tree.errors.append(f"{shard.shard_id}: retracted but still in data/")
        if not shard.active and shard.shard_id not in retracted_ids:
            tree.errors.append(f"{shard.shard_id}: in retracted/ without a retracted event")
        if shard.active and shard.shard_id not in supported:
            tree.errors.append(f"{shard.shard_id}: no produced, confirmed or inherited event")
    seen: dict[tuple[str, Key], tuple[str, object]] = {}
    for shard in tree.shards.values():
        if not shard.active:
            continue
        for key, out in shard.rows.items():
            previous = seen.setdefault((shard.quantity, key), (shard.shard_id, out))
            if previous[1] != out:
                tree.errors.append(f"{shard.shard_id}: key {key} conflicts with {previous[0]}")
    return tree.errors


def _in_repository(tree: Tree, system: str) -> bool:
    return bool(tree.systems.get(system, {}).get("in_repository"))


def _is_hex(text: str, length: int) -> bool:
    return len(text) == length and all(c in "0123456789abcdef" for c in text)


def _buggy_recipe(tree: Tree, recipe: object) -> bool:
    """Whether the recipe was retired because it contained a bug (its reproductions do not count)."""
    return any(
        e["event"] == "recipe_retired" and e.get("recipe") == recipe and e.get("reason") == "bug"
        for e in tree.events
    )


def row_support(tree: Tree, shard: Shard) -> dict[Key, list[frozenset[str]]]:
    """For each row, the assumption sets of the events supporting it (own and inherited)."""
    support: dict[Key, list[frozenset[str]]] = {key: [] for key in shard.rows}

    def own(shard_id: str) -> list[frozenset[str]]:
        sets: list[frozenset[str]] = []
        for event in tree.events:
            if event.get("shard") == shard_id and event["event"] in SUPPORT_EVENTS:
                if not _buggy_recipe(tree, event.get("recipe")):
                    sets.append(frozenset(str(a) for a in _as_list(event.get("assumes"))))  # pyright: ignore[reportUnknownVariableType, reportAttributeAccessIssue, reportUnknownArgumentType]
        return sets

    for key in shard.rows:
        support[key].extend(own(shard.shard_id))
    for event in tree.events:
        if event["event"] == "inherited" and event.get("shard") == shard.shard_id:
            source = tree.shards.get(str(event.get("source")))
            if source is None:
                continue
            excluded = {tuple(_freeze(k) for k in _as_list(key)) for key in _as_list(event.get("excluded"))}
            inherited = row_support(tree, source)
            for key in shard.rows:
                if key in source.rows and key not in excluded:
                    support[key].extend(inherited[key])
    return support


def minimal_sets(sets: list[frozenset[str]]) -> list[frozenset[str]]:
    unique = set(sets)
    return sorted((s for s in unique if not any(t < s for t in unique)), key=sorted)


def status(tree: Tree) -> dict[str, str]:
    """Per active shard: 'unconditional', 'conditional on ...' (weakest row) or 'unsupported'."""
    result: dict[str, str] = {}
    for shard in tree.shards.values():
        if not shard.active:
            continue
        worst = "unconditional"
        for sets in row_support(tree, shard).values():
            if not sets:
                worst = "unsupported"
                break
            minimal = minimal_sets(sets)
            if frozenset() not in minimal:
                worst = "conditional on " + " or ".join("+".join(sorted(s)) for s in minimal)
        result[shard.shard_id] = worst
    return result
