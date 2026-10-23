"""Command line: python -m tools.reference {check,status,produce,confirm,retire-recipe}.

check                         consistency of reference/ (exit status 1 on problems)
status                        derived status of every active shard
produce RECIPE INPUTS SHARD   compute a new shard (INPUTS: JSONL of key fields)
confirm RECIPE SHARD          recompute a shard and record confirmed/disagreed
retire-recipe RECIPE {outdated,bug} EXPLANATION
                              move a recipe to recipes-retired/ and record why
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
    k = sub.add_parser("check")
    k.add_argument("--no-git", action="store_true", help="skip the checks against the git history")
    sub.add_parser("status")
    p = sub.add_parser("produce")
    p.add_argument("recipe")
    p.add_argument("inputs", type=pathlib.Path)
    p.add_argument("shard")
    c = sub.add_parser("confirm")
    c.add_argument("recipe")
    c.add_argument("shard")
    r = sub.add_parser("retire-recipe")
    r.add_argument("recipe")
    r.add_argument("reason", choices=["outdated", "bug"])
    r.add_argument("explanation")
    args = parser.parse_args(argv)
    tree = model.load(args.root)
    if args.command == "check":
        problems = model.check(tree)
        if not args.no_git:
            problems += run.check_git(tree)
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
    elif args.command == "retire-recipe":
        run.retire_recipe(tree, args.recipe, args.reason, args.explanation)
    else:
        mismatches = run.confirm(tree, args.recipe, args.shard)
        print(f"{len(mismatches)} mismatches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
