"""Running recipes and appending provenance events."""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import pathlib
import socket
import subprocess
import tempfile
from typing import Any

from tools.reference.model import REPRODUCTION_EVENTS, Key, Tree, sha256

TOOL_PATHS = ("tools", "crosscheck")

REPO = pathlib.Path(__file__).resolve().parents[2]
CROSSCHECK = REPO / "crosscheck"


def git(*args: str) -> str:
    """Run git in the repository and return its stripped output."""
    proc = subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, check=True)
    return proc.stdout.strip()


def require_clean_tree() -> None:
    """Refuse to record anything while the working tree has uncommitted changes."""
    if git("status", "--porcelain"):
        raise SystemExit("refusing to record provenance: the working tree has uncommitted changes")


def tool_commit() -> str:
    """The commit of origin/main, provided the tooling at HEAD is identical to it.

    Only tooling already merged on main may record provenance; reproductions themselves may
    be recorded on a branch (their software is identified by source hashes).
    """
    require_clean_tree()
    git("fetch", "--quiet", "origin", "main")
    main = git("rev-parse", "FETCH_HEAD")
    changed = git("diff", "--name-only", main, "HEAD", "--", *TOOL_PATHS)
    if changed:
        raise SystemExit(f"refusing to record provenance: the tooling differs from origin/main:\n{changed}")
    return main


def source_hash(sources: list[str], commit: str = "HEAD") -> str:
    """The system version of an in-repository system: sha256 over the git object ids of its sources.

    The text hashed is one line ``<path> <git object id at commit>`` per source, in the order of
    systems.toml. It depends only on the content of the sources, not on the commit, so it is the
    same before and after any kind of merge.
    """
    lines = [f"{path} {git('rev-parse', f'{commit}:{path}')}" for path in sources]
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def evaluate_python(
    tree: Tree, system: str, template: str, inputs: list[dict[str, Any]]
) -> tuple[list[object], str]:
    """Evaluate an arithkit_toy/arithkit recipe in this process; returns the outputs and the version."""
    if system == "arithkit_toy":
        from arithkit_toy.modular import quotient
    elif system == "arithkit":
        from arithkit.modular import quotient
    else:
        raise ValueError(system)
    namespace = {
        "GL2ASubQuotient": quotient.GL2ASubQuotient,
        "GL2QSubQuotient": quotient.GL2QSubQuotient,
    }
    outputs = [eval(f"({template})", {**namespace, **row}) for row in inputs]
    sources = tree.systems[system]["sources"]
    assert isinstance(sources, list)
    return outputs, source_hash([str(x) for x in sources])  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]


def _clean_environment() -> dict[str, str]:
    """os.environ without our virtualenv and active conda env, so CAS envs activate cleanly."""
    drop_prefixes = [str(REPO / ".venv")]
    if "CONDA_PREFIX" in os.environ:
        drop_prefixes.append(os.environ["CONDA_PREFIX"])
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("VIRTUAL_ENV", "PYTHONPATH", "PYTHONHOME") and not k.startswith(("CONDA_", "UV_"))
    }
    path = env.get("PATH", "").split(os.pathsep)
    env["PATH"] = os.pathsep.join(p for p in path if not any(p.startswith(d) for d in drop_prefixes))
    return env


def evaluate_external(
    system: str, recipe_path: pathlib.Path, inputs: list[dict[str, Any]]
) -> tuple[list[object], str]:
    """Evaluate a recipe of an external system through crosscheck/<system>/run.py."""
    runner = CROSSCHECK / system / "run.py"
    if not runner.exists():
        raise SystemExit(f"no runner for system {system!r}")
    # Run inside the activated Sage conda env, with our virtualenv removed from the environment.
    command = {"sage": ["/opt/sage/bin/conda", "run", "-n", "sage", "python"]}.get(system)
    if command is None:
        raise SystemExit(f"do not know how to start {system!r}")
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", dir=REPO / "tmp", delete=False) as f:
        f.write("\n".join(json.dumps(row) for row in inputs) + "\n")
        inputs_path = pathlib.Path(f.name)
    try:
        proc = subprocess.run(
            [*command, str(runner), str(recipe_path), str(inputs_path)],
            capture_output=True,
            text=True,
            check=False,
            env=_clean_environment(),
        )
    finally:
        inputs_path.unlink()
    if proc.returncode != 0:
        raise SystemExit(f"{system} runner failed:\n{proc.stderr}")
    lines = proc.stdout.strip().splitlines()
    version = json.loads(lines[0])["version"]
    return [json.loads(line) for line in lines[1:]], version


def run_recipe(tree: Tree, recipe_id: str, inputs: list[dict[str, Any]]) -> tuple[list[object], str]:
    recipe = tree.recipes[recipe_id]
    system = str(recipe["system"])
    if tree.recipe_paths[recipe_id].parent.parent.name != "recipes":
        raise SystemExit(f"{recipe_id} is retired; only recipes in recipes/ can be run")
    if system in ("arithkit_toy", "arithkit"):
        return evaluate_python(tree, system, str(recipe["template"]), inputs)
    return evaluate_external(system, tree.recipe_paths[recipe_id], inputs)


def append_event(tree: Tree, quantity: str, event: dict[str, object], commit: str) -> None:
    """Append an event; ``commit`` is the clean HEAD determined before anything was written."""
    event = {
        **event,
        "date": datetime.date.today().isoformat(),
        "host": socket.gethostname(),
        "tool_commit": commit,
    }
    path = tree.root / "provenance" / f"{quantity}.jsonl"
    with path.open("a") as f:
        f.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")


def produce(tree: Tree, recipe_id: str, inputs_path: pathlib.Path, shard_id: str) -> None:
    """Compute a new shard from a JSONL file of inputs and record a `produced` event."""
    recipe = tree.recipes[recipe_id]
    quantity = str(recipe["quantity"])
    target = tree.root / "data" / shard_id
    if target.exists() or (tree.root / "retracted" / shard_id).exists():
        raise SystemExit(f"shard {shard_id} exists already; shards are immutable")
    if not shard_id.startswith(quantity + "/"):
        raise SystemExit(f"shard id must start with {quantity}/")
    commit = tool_commit()
    inputs = [json.loads(line) for line in inputs_path.read_text().splitlines() if line.strip()]
    outputs, version = run_recipe(tree, recipe_id, inputs)
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps({"format": 1, "quantity": quantity}, sort_keys=True, separators=(",", ":"))]
    lines += [
        json.dumps({**row, "out": out}, sort_keys=True, separators=(",", ":"))
        for row, out in zip(inputs, outputs, strict=True)
    ]
    target.write_text("\n".join(lines) + "\n")
    _record(tree, "produced", recipe_id, shard_id, version, [], commit)


def confirm(tree: Tree, recipe_id: str, shard_id: str) -> list[Key]:
    """Recompute an active shard with a recipe; record `confirmed` or `disagreed` (with the keys)."""
    shard = tree.shards[shard_id]
    commit = tool_commit()
    quantity = tree.quantities[shard.quantity]
    fields = [str(f) for f in quantity["key"]]  # pyright: ignore[reportGeneralTypeIssues, reportUnknownVariableType]
    keys = list(shard.rows)
    inputs = [dict(zip(fields, key, strict=True)) for key in keys]
    outputs, version = run_recipe(tree, recipe_id, inputs)
    mismatches = [key for key, out in zip(keys, outputs, strict=True) if shard.rows[key] != out]
    _record(
        tree, "disagreed" if mismatches else "confirmed", recipe_id, shard_id, version, mismatches, commit
    )
    return mismatches


def _record(
    tree: Tree, kind: str, recipe_id: str, shard_id: str, version: str, mismatches: list[Key], commit: str
) -> None:
    recipe = tree.recipes[recipe_id]
    event: dict[str, object] = {
        "event": kind,
        "shard": shard_id,
        "sha256": sha256(tree.root / "data" / shard_id),
        "recipe": recipe_id,
        "recipe_sha256": sha256(tree.recipe_paths[recipe_id]),
        "system": recipe["system"],
        "system_version": version,
        "assumes": recipe["assumes"],
    }
    if kind == "disagreed":
        event["mismatches"] = [list(k) for k in mismatches]
    append_event(tree, str(recipe["quantity"]), event, commit)


def retire_recipe(tree: Tree, recipe_id: str, reason: str, explanation: str) -> None:
    """Move a recipe to recipes-retired/ and record why ("outdated" or "bug")."""
    if recipe_id not in tree.recipes or recipe_id in tree.retired:
        raise SystemExit(f"{recipe_id!r} is not an active recipe")
    if reason not in ("outdated", "bug"):
        raise SystemExit("reason must be 'outdated' or 'bug'")
    commit = tool_commit()
    source = tree.recipe_paths[recipe_id]
    target = tree.root / "recipes-retired" / source.parent.name / source.name
    target.parent.mkdir(parents=True, exist_ok=True)
    git("mv", str(source), str(target))
    event: dict[str, object] = {
        "event": "recipe_retired",
        "recipe": recipe_id,
        "reason": reason,
        "explanation": explanation,
    }
    append_event(tree, str(tree.recipes[recipe_id]["quantity"]), event, commit)


def check_git(tree: Tree) -> list[str]:
    """Checks against the git history: tool commits are ancestors of HEAD, and the source hash of
    every reproduction by an in-repository system occurs at some commit reachable from HEAD."""
    problems: list[str] = []
    commits = git("rev-list", "HEAD").split()
    known: dict[str, set[str]] = {}
    for number, event in enumerate(tree.events, start=1):
        commit = str(event.get("tool_commit"))
        ok = subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, "HEAD"], cwd=REPO, capture_output=True
        )
        if ok.returncode != 0:
            problems.append(f"event {number}: tool_commit {commit} is not an ancestor of HEAD")
        system = str(event.get("system"))
        sources = tree.systems.get(system, {}).get("sources")
        if event["event"] in REPRODUCTION_EVENTS and isinstance(sources, list):
            if system not in known:
                hashes: set[str] = set()
                for c in commits:
                    try:
                        hashes.add(source_hash([str(x) for x in sources], c))  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
                    except subprocess.CalledProcessError:
                        continue
                known[system] = hashes
            if event.get("system_version") not in known[system]:
                problems.append(
                    f"event {number}: source hash of {system} occurs at no commit of HEAD's history"
                )
    return problems
