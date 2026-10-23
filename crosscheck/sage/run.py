"""Evaluate a Sage recipe (reference/recipes/sage/*.toml) on the inputs in a JSONL file.

Run with the Python of the Sage conda env, e.g.
    /opt/sage/bin/conda run -n sage python crosscheck/sage/run.py RECIPE.toml INPUTS.jsonl
Prints {"version": ...} and then one JSON output per input line.
"""

import json
import sys
import tomllib

import sage.all as sage_all
from sage.version import version


def main() -> None:
    with open(sys.argv[1], "rb") as f:
        recipe = tomllib.load(f)
    template = recipe["template"].strip()
    namespace = {name: getattr(sage_all, name) for name in dir(sage_all) if not name.startswith("_")}
    print(json.dumps({"version": version}))
    with open(sys.argv[2]) as f:
        lines = f.read().splitlines()
    for line in lines:
        if not line.strip():
            continue
        row = json.loads(line)
        value = eval(f"({template})", {**namespace, **row})
        print(json.dumps(int(value)))


if __name__ == "__main__":
    main()
