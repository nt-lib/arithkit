"""Running recipes and appending provenance events."""

from __future__ import annotations

import datetime
import json
import os
import pathlib
import socket
import subprocess
import sys
import tempfile
from typing import Any

from tools.reference.model import Key, Tree, sha256

REPO = pathlib.Path(__file__).resolve().parents[2]
CROSSCHECK = REPO / "crosscheck"


def tool_commit() -> str:
    """HEAD of this repository; refuses a working tree with uncommitted changes."""
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], cwd=REPO, capture_output=True, text=True, check=True
    )
    if dirty.stdout.strip():
        raise SystemExit("refusing to record provenance: the working tree has uncommitted changes")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True, check=True)
    return head.stdout.strip()


def evaluate_python(system: str, template: str, inputs: list[dict[str, Any]]) -> tuple[list[object], str]:
    """Evaluate a toy/arithkit recipe in this process; returns the outputs and the system version."""
    if system == "toy":
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
    return outputs, f"{system} 0.1.0 (python {sys.version.split()[0]})"


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
    if system in ("toy", "arithkit"):
        return evaluate_python(system, str(recipe["template"]), inputs)
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
        "system_version": version,
        "assumes": recipe["assumes"],
    }
    if kind == "disagreed":
        event["mismatches"] = [list(k) for k in mismatches]
    append_event(tree, str(recipe["quantity"]), event, commit)


def retract_recipe(tree: Tree, recipe_id: str, reason: str) -> None:
    """Record that events of ``recipe_id`` no longer count as support."""
    if recipe_id not in tree.recipes:
        raise SystemExit(f"unknown recipe {recipe_id!r}")
    commit = tool_commit()
    event: dict[str, object] = {"event": "retracted_recipe", "recipe": recipe_id, "reason": reason}
    append_event(tree, str(tree.recipes[recipe_id]["quantity"]), event, commit)
