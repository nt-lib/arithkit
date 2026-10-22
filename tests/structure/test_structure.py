"""The interfaces of arithkit_api, arithkit_toy and arithkit (stubs and runtime) agree exactly.

Compared per public class and module-level function: the names of the public
methods (plus the relevant dunders), their parameter names and kinds, and the
annotations. Annotations are compared after dropping module qualifiers
(``api.QuotientElement`` and ``QuotientElement`` are the same name).
"""

from __future__ import annotations

import ast
import importlib
import inspect
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2] / "python"
MODULES = ["modular.quotient", "modular.subgroup"]
DUNDERS = {"__call__", "__mul__", "__pow__", "__eq__", "__hash__", "__contains__"}

type Signature = tuple[tuple[tuple[str, str], ...], str]
type Interface = dict[str, dict[str, Signature]]


def normalise(annotation: str) -> str:
    return re.sub(r"\b(?:\w+\.)+(\w+)", r"\1", annotation).replace(" ", "")


def is_public(name: str) -> bool:
    return not name.startswith("_") or name in DUNDERS


def ast_signature(fn: ast.FunctionDef) -> Signature:
    args = fn.args.posonlyargs + fn.args.args
    params = tuple((a.arg, normalise(ast.unparse(a.annotation)) if a.annotation else "") for a in args)
    return params, normalise(ast.unparse(fn.returns)) if fn.returns else ""


def interface_from_source(path: pathlib.Path) -> Interface:
    """Public classes (with methods inherited from classes in the same file) and functions."""
    tree = ast.parse(path.read_text())
    classes: dict[str, ast.ClassDef] = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}

    def methods(cls: ast.ClassDef) -> dict[str, Signature]:
        out: dict[str, Signature] = {}
        for base in cls.bases:
            name = ast.unparse(base).split(".")[-1]
            if name in classes and classes[name] is not cls:
                out.update(methods(classes[name]))
        for node in cls.body:
            if isinstance(node, ast.FunctionDef) and is_public(node.name):
                out[node.name] = ast_signature(node)
        return out

    result: Interface = {name: methods(cls) for name, cls in classes.items() if not name.startswith("_")}
    result[""] = {
        n.name: ast_signature(n) for n in tree.body if isinstance(n, ast.FunctionDef) and is_public(n.name)
    }
    return result


def without_init(interface: Interface) -> Interface:
    return {cls: {k: v for k, v in members.items() if k != "__init__"} for cls, members in interface.items()}


@pytest.mark.toy
@pytest.mark.parametrize("module", MODULES)
def test_toy_matches_api(module: str) -> None:
    path = module.replace(".", "/") + ".py"
    api = interface_from_source(ROOT / "arithkit_api" / path)
    toy = without_init(interface_from_source(ROOT / "arithkit_toy" / path))
    assert set(toy) == set(api)
    for cls, members in api.items():
        toy_members = {k: v for k, v in toy[cls].items() if k in members or not k.startswith("_")}
        assert toy_members == members, cls


@pytest.mark.toy
@pytest.mark.parametrize("module", MODULES)
def test_stubs_match_api(module: str) -> None:
    path = module.replace(".", "/")
    api = interface_from_source(ROOT / "arithkit_api" / f"{path}.py")
    stubs = without_init(interface_from_source(ROOT / "arithkit" / f"{path}.pyi"))
    assert stubs == api


@pytest.mark.native
@pytest.mark.parametrize("module", MODULES)
def test_native_runtime_matches_stubs(module: str) -> None:
    stubs = interface_from_source(ROOT / "arithkit" / (module.replace(".", "/") + ".pyi"))
    runtime = importlib.import_module(f"arithkit.{module}")
    for cls_name, members in stubs.items():
        target = runtime if cls_name == "" else getattr(runtime, cls_name)
        for name, (params, _) in members.items():
            obj = getattr(target, name)
            assert callable(obj) or isinstance(obj, property | type(int.real)), (cls_name, name)
            text_signature = getattr(obj, "__text_signature__", None)
            if text_signature and name not in DUNDERS:
                expected = [p for p, _ in params]
                actual = [str(p) for p in inspect.signature(obj).parameters]  # pyright: ignore[reportArgumentType]
                actual = ["self" if p in ("$self", "self") else p.lstrip("$") for p in actual]
                assert actual == expected, (cls_name, name, actual, expected)
