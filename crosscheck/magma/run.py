"""Evaluate a Magma recipe (reference/recipes/magma/*.toml) on the inputs in a JSONL file.

Usage: python crosscheck/magma/run.py RECIPE.toml INPUTS.jsonl
The recipe's template is a Magma expression with Python format fields for the key fields of the
quantity (e.g. {N}, {M}, {I}, {kind}). All rows are evaluated in one Magma run (`magma -n`, stdin
from /dev/null). Prints {"version": ...} and then one JSON output per input line.
"""

import json
import pathlib
import subprocess
import sys
import tempfile
import tomllib

MAGMA = "magma"
TMP = pathlib.Path(__file__).resolve().parents[1] / "tmp"


def main() -> None:
    with open(sys.argv[1], "rb") as f:
        recipe = tomllib.load(f)
    rows = [json.loads(line) for line in pathlib.Path(sys.argv[2]).read_text().splitlines() if line.strip()]
    template = recipe["template"].strip()
    lines = ['a, b, c := GetVersion(); printf "VERSION %o.%o-%o\\n", a, b, c;']
    for row in rows:
        lines.append(f'printf "VALUE %o\\n", {template.format(**row)};')
    lines.append("quit;")
    TMP.mkdir(exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".m", dir=TMP, delete=False) as script:
        script.write("\n".join(lines) + "\n")
    try:
        with open("/dev/null") as devnull:
            proc = subprocess.run(
                [MAGMA, "-n", script.name], stdin=devnull, capture_output=True, text=True, check=False
            )
    finally:
        pathlib.Path(script.name).unlink()
    out = proc.stdout.splitlines()
    versions = [line.split()[1] for line in out if line.startswith("VERSION ")]
    values = [int(line.split()[1]) for line in out if line.startswith("VALUE ")]
    if proc.returncode != 0 or len(versions) != 1 or len(values) != len(rows):
        sys.stderr.write(proc.stdout + proc.stderr)
        raise SystemExit("magma failed")
    print(json.dumps({"version": versions[0]}))
    for value in values:
        print(json.dumps(value))


if __name__ == "__main__":
    main()
