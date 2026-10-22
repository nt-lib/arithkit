"""Command line: python -m tools.reference {check,status,produce,confirm}.

check                         consistency of reference/ (exit status 1 on problems)
status                        derived status of every active shard
produce RECIPE INPUTS SHARD   compute a new shard (INPUTS: JSONL of key fields)
confirm RECIPE SHARD          recompute a shard and record confirmed/disagreed
"""

from __future__ import annotations

import argparse
import pathlib
import sys

from tools.reference import model, run

DEFAULT_ROOT = pathlib.Path(__file__).resolve().parents[2] / "reference"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tools.reference")
    parser.add_argument("--root", type=pathlib.Path, default=DEFAULT_ROOT)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check")
    sub.add_parser("status")
    p = sub.add_parser("produce")
    p.add_argument("recipe")
    p.add_argument("inputs", type=pathlib.Path)
    p.add_argument("shard")
    c = sub.add_parser("confirm")
    c.add_argument("recipe")
    c.add_argument("shard")
    args = parser.parse_args(argv)
    tree = model.load(args.root)
    if args.command == "check":
        problems = model.check(tree)
        for problem in problems:
            print(problem)
        print(f"{len(tree.shards)} shards, {len(tree.events)} events, {len(problems)} problems")
        return 1 if problems else 0
    if args.command == "status":
        for shard_id, state in sorted(model.status(tree).items()):
            print(f"{shard_id}: {state}")
        return 0
    if model.check(tree):
        print("the reference tree is inconsistent; run check first", file=sys.stderr)
        return 1
    if args.command == "produce":
        run.produce(tree, args.recipe, args.inputs, args.shard)
    else:
        mismatches = run.confirm(tree, args.recipe, args.shard)
        print(f"{len(mismatches)} mismatches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
