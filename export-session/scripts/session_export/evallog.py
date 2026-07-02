# -*- coding: utf-8 -*-
"""evallog — append one self-eval entry to ``export-session-eval-log.md`` per the
file's own maintenance protocol (design §9), comparing this run to the last.

Guardrails baked in (design §13.4):
* **Idempotent** — each entry embeds ``<!-- eval-key:<session>|<generated_at> -->``;
  appending the same key twice is a no-op (returns ``False``).
* **Concurrency-safe** — the read-modify-append happens under an exclusive
  cross-process file lock (``O_CREAT|O_EXCL`` lockfile), so simultaneous triggers
  serialise instead of clobbering each other.
"""
import json
import os
import re
import time
from contextlib import contextmanager
from pathlib import Path

from . import config

_STATS_RE = re.compile(r"<!-- eval-stats:(\{.*?\}) -->")
_RUN_RE = re.compile(r"·\s*run\s+(\d+)\s*·")


def entry_key(session_id, generated_at):
    return "%s|%s" % (session_id, generated_at)


def _key_marker(key):
    return "<!-- eval-key:%s -->" % key


def _arrow(cur, prev):
    if prev is None:
        return "-(无上次)"
    if cur > prev:
        return "↑"
    if cur < prev:
        return "↓"
    return "-"


def _misreject_num(stats):
    return stats["misrejected"] / stats["unselected"] if stats["unselected"] else 0.0


def build_entry(*, run_number, generated_at, trigger, session_id, stats, health,
                conclusion, next_suggestion, prev=None):
    """Render one maintenance-protocol entry (with idempotency + comparison markers)."""
    key = entry_key(session_id, generated_at)
    d2_hits = (stats["d2_hallucination"] + stats["d2_misread"]
               + stats["d2_incomplete"] + stats["d2_inaccurate"])
    marker_stats = {"run": run_number, "misreject_num": round(_misreject_num(stats), 4),
                    "d1_suggestions": stats["d1_suggestions"], "d2_hits": d2_hits}

    prev_mr = prev.get("misreject_num") if prev else None
    prev_d1 = prev.get("d1_suggestions") if prev else None
    prev_d2 = prev.get("d2_hits") if prev else None

    lines = [
        "## %s · run %d · D1+D2" % (generated_at, run_number),
        _key_marker(key),
        "<!-- eval-stats:%s -->" % json.dumps(marker_stats, ensure_ascii=False, sort_keys=True),
        "- 触发:%s;会话 session_id=%s" % (trigger, session_id),
        "- 选择:选中 %d / 未选 %d(事后判误退 %d);误退率 %s" % (
            stats["selected"], stats["unselected"], stats["misrejected"], stats["misreject_rate"]),
        "- D1:发现 skill/MCP 问题 %d 条,可执行建议 %d 条,归因完整度 %s" % (
            stats["d1_problems"], stats["d1_suggestions"], health["attribution"]),
        "- D2:幻觉 %d / 误解 %d / wiki 不完整 %d / 不准确 %d / 低置信疑似 %d;"
        "建议是否落到具体页段 %s;是否已转 /wiki-refine %s" % (
            stats["d2_hallucination"], stats["d2_misread"], stats["d2_incomplete"],
            stats["d2_inaccurate"], stats["d2_low_confidence"],
            health["d2_page_specific"], health["routed"]),
        "- 流程健康:递归自噬 %s;超时 %s;解析失败 %s;时长 %s;会话规模 %s" % (
            health["recursion"], health["timeout"], health["parse_errors"],
            health["duration"], health["scale"]),
        "- 对比上次:误退率 %s ;D1 建议数 %s;D2 命中 %s" % (
            _arrow(_misreject_num(stats), prev_mr), _arrow(stats["d1_suggestions"], prev_d1),
            _arrow(d2_hits, prev_d2)),
        "- 结论:%s" % conclusion,
        "- 下次建议:%s" % next_suggestion,
    ]
    return "\n".join(lines) + "\n"


def parse_last_run(log_text):
    """Return the last entry's machine-readable stats dict, or ``None`` (e.g. bootstrap)."""
    matches = _STATS_RE.findall(log_text or "")
    if not matches:
        return None
    try:
        return json.loads(matches[-1])
    except ValueError:
        return None


def next_run_number(log_text):
    """Next ``run <n>`` = max existing run number + 1 (bootstrap run 0 → 1; none → 1)."""
    nums = [int(n) for n in _RUN_RE.findall(log_text or "")]
    return (max(nums) + 1) if nums else 1


@contextmanager
def file_lock(lock_path, timeout=10.0, poll=0.02):
    """Exclusive cross-process lock via an ``O_CREAT|O_EXCL`` lockfile (design §13.4)."""
    lock_path = Path(lock_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    fd = None
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise TimeoutError("could not acquire lock %s within %ss" % (lock_path, timeout))
            time.sleep(poll)
    try:
        yield
    finally:
        os.close(fd)
        try:
            os.unlink(str(lock_path))
        except OSError:
            pass


def append_entry(log_path, entry_text, *, key, lock_timeout=10.0):
    """Append ``entry_text`` under the file lock; skip (return ``False``) if ``key`` present."""
    log_path = Path(log_path)
    lock_path = log_path.with_name(log_path.name + ".lock")
    with file_lock(lock_path, timeout=lock_timeout):
        existing = config.read_text(log_path) if log_path.is_file() else ""
        if key and _key_marker(key) in existing:
            return False
        body = entry_text if not existing else (existing.rstrip("\n") + "\n\n" + entry_text)
        config.write_text(log_path, body)
        return True
