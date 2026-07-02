# -*- coding: utf-8 -*-
"""Pytest bootstrap: make ``session_export`` and the test ``builders`` importable
regardless of the invocation cwd."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent          # .../scripts
for p in (HERE, HERE / "tests"):
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)
