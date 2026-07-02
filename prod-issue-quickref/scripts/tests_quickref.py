# -*- coding: utf-8 -*-
"""Standalone self-tests for validate_quickref.py and quickref_hook.py.
Run: python -X utf8 tests_quickref.py   (exit 0 = all pass)
"""
import io
import os
import sys
import tempfile
import contextlib
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


vq = _load("validate_quickref")
hk = _load("quickref_hook")
hk.STATE_DIR = tempfile.mkdtemp(prefix="qrtest-")  # isolate markers

fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)


# ---------- validator ----------
GOOD = (
    "---\ntitle: x 生产问题速查\n---\n# t\n"
    "## 现象A\n"
    "- **判别**：sig `Foo`\n"
    "  - **根因**：cause. **确认** → [d](./sub/architecture.md#a)\n"
)
r = vq.validate(GOOD)
check(r["ok"] and r["roots"] == 1, "validator GOOD should pass -> %s" % r)

r = vq.validate(GOOD.replace("[d](./sub/architecture.md#a)", "见架构文档"))
check(not r["ok"], "validator missing-link should FAIL")

r = vq.validate(GOOD + "\n???")
check(not r["ok"], "validator mojibake should FAIL")

r = vq.validate("no frontmatter here")
check(not r["ok"], "validator no-frontmatter should FAIL")


# ---------- hook ----------
def run_stop(data):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        hk.do_stop(data)
    return buf.getvalue()


check(run_stop({"session_id": "s1"}) == "", "unarmed stop must be silent")

hk.do_arm({"tool_name": "Read", "tool_input": {"file_path": "D:/w/生产问题速查.md"}, "session_id": "s2"})
check(os.path.exists(os.path.join(hk.STATE_DIR, "s2.armed")), "arm on 速查 Read must create marker")

hk.do_arm({"tool_name": "Read", "tool_input": {"file_path": "D:/w/other.md"}, "session_id": "s3"})
check(not os.path.exists(os.path.join(hk.STATE_DIR, "s3.armed")), "non-速查 Read must NOT arm")

out = run_stop({"session_id": "s2"})
check('"decision"' in out and "block" in out, "armed stop must block once -> %r" % out[:40])

check(run_stop({"session_id": "s2"}) == "", "second stop must be silent (.done loop guard)")

hk.do_arm({"tool_name": "Read", "tool_input": {"file_path": "x/生产问题速查.md"}, "session_id": "s4"})
check(run_stop({"session_id": "s4", "stop_hook_active": True}) == "",
      "stop_hook_active must be silent even if armed")

check(hk.do_arm({}) == 0 and hk.do_stop({}) == 0, "empty input must be fail-open (exit 0)")

print("FAILS:", fails if fails else "NONE")
sys.exit(1 if fails else 0)
