"""Shared fixtures: the backend fixture runs a test against the toy and the native implementation."""

from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from types import ModuleType

import pytest
from hypothesis import HealthCheck, settings

settings.register_profile(
    "ci", derandomize=True, max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow]
)
settings.register_profile(
    "nightly", max_examples=1000, deadline=None, suppress_health_check=list(HealthCheck)
)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "ci"))

PACKAGES = {"toy": "arithkit_toy", "native": "arithkit"}


@dataclass(frozen=True)
class Backend:
    """The modules of one implementation."""

    name: str
    quotient: ModuleType
    subgroup: ModuleType


def load_backend(name: str) -> Backend:
    """The modules of the implementation ``name`` ("toy" or "native")."""
    package = PACKAGES[name]
    return Backend(
        name,
        importlib.import_module(f"{package}.modular.quotient"),
        importlib.import_module(f"{package}.modular.subgroup"),
    )


BACKEND_PARAMS = [
    pytest.param("toy", marks=pytest.mark.toy),
    pytest.param("native", marks=pytest.mark.native),
]


@pytest.fixture(params=BACKEND_PARAMS)
def backend(request: pytest.FixtureRequest) -> Backend:
    """Each implementation in turn."""
    name: str = request.param
    return load_backend(name)
