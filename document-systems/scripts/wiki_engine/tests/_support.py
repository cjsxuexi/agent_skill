"""Shared test bootstrap: put the ``scripts/`` dir (parent of ``wiki_engine``) on
sys.path so ``from wiki_engine import ...`` resolves under the plan's exact command
``python -X utf8 -m unittest discover document-systems/scripts/wiki_engine/tests``.

The ``tests/`` directory is the discover top-level dir, so this module is importable
by every test as ``import _support``.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.dirname(os.path.dirname(_HERE))  # scripts/
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

FIXTURES = os.path.join(_HERE, "fixtures")


def fixture(name):
    return os.path.join(FIXTURES, name)


def read_fixture(name):
    with open(fixture(name), "rb") as fh:
        return fh.read().decode("utf-8")
