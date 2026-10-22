"""Ctrl-C interrupts long native computations (Cargo feature `interrupt`, on by default)."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time

import pytest

pytestmark = [
    pytest.mark.native,
    pytest.mark.skipif(
        os.environ.get("ARITHKIT_NO_INTERRUPT") == "1", reason="built with --no-default-features"
    ),
]

SCRIPT = """
import sys
from arithkit.modular.quotient import AdelicQuotient
print("start", flush=True)
try:
    AdelicQuotient(1, 1000).elements()
except KeyboardInterrupt:
    print("interrupted", flush=True)
    sys.exit(3)
sys.exit(0)
"""


def test_sigint_interrupts_enumeration() -> None:
    proc = subprocess.Popen(
        [sys.executable, "-c", SCRIPT], stdout=subprocess.PIPE, text=True, env=os.environ.copy()
    )
    assert proc.stdout is not None
    assert proc.stdout.readline().strip() == "start"
    time.sleep(0.5)
    proc.send_signal(signal.SIGINT)
    try:
        code = proc.wait(timeout=20)
    finally:
        proc.kill()
    assert code == 3
    assert proc.stdout.read().strip() == "interrupted"
