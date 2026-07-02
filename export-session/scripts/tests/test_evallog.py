# -*- coding: utf-8 -*-
"""evallog: append one self-eval entry per the maintenance protocol — idempotent by
key, this-vs-last comparison, and a file lock for concurrent triggers (design §9/§13.4)."""
import threading

import pytest

from session_export import evallog


def _stats():
    return {"selected": 2, "unselected": 1, "misrejected": 0, "misreject_rate": "0/1",
            "d1_problems": 1, "d1_suggestions": 1, "d2_total": 1, "d2_hallucination": 0,
            "d2_misread": 0, "d2_incomplete": 0, "d2_inaccurate": 0, "d2_low_confidence": 1}


def _health():
    return {"attribution": "中(基线)", "recursion": "无", "timeout": "无", "parse_errors": "无",
            "duration": "0.1s", "scale": "5 条", "d2_page_specific": "否", "routed": "否"}


def _entry(run_number=1, session_id="s1", generated_at="2026-07-02T09:00:00Z", prev=None):
    return evallog.build_entry(
        run_number=run_number, generated_at=generated_at, trigger="comment",
        session_id=session_id, stats=_stats(), health=_health(),
        conclusion="首次真实分析,作为基线", next_suggestion="补 fixture 覆盖 D2 幻觉判定", prev=prev)


def test_build_entry_has_protocol_lines_and_markers():
    e = _entry(run_number=3)
    assert "· run 3 · D1+D2" in e
    assert evallog.entry_key("s1", "2026-07-02T09:00:00Z") in e     # idempotency key marker
    assert "<!-- eval-stats:" in e                                   # machine-readable comparison state
    assert "触发:comment" in e and "session_id=s1" in e
    assert "误退率 0/1" in e
    assert "发现 skill/MCP 问题 1 条" in e
    assert "低置信疑似 1" in e
    assert "递归自噬 无" in e
    assert "对比上次" in e and "结论:" in e and "下次建议:" in e


def test_append_creates_and_is_idempotent(tmp_path):
    log = tmp_path / "eval.md"
    log.write_text("# log\n", encoding="utf-8")
    e = _entry()
    key = evallog.entry_key("s1", "2026-07-02T09:00:00Z")
    assert evallog.append_entry(log, e, key=key) is True
    first = log.read_text(encoding="utf-8")
    assert evallog.append_entry(log, e, key=key) is False           # same key → no-op
    assert log.read_text(encoding="utf-8") == first                 # file unchanged
    assert first.count("<!-- eval-key:") == 1


def test_next_run_number_after_bootstrap():
    boot = "## 2026-07-01 · run 0 · bootstrap(设计定稿)\n- 触发:—\n"
    assert evallog.next_run_number(boot) == 1
    assert evallog.next_run_number("# empty log\n") == 1            # no runs yet → run 1
    assert evallog.parse_last_run(boot) is None                    # bootstrap has no stats marker


def test_parse_last_run_reads_stats_marker(tmp_path):
    log = tmp_path / "eval.md"
    log.write_text("# log\n", encoding="utf-8")
    evallog.append_entry(log, _entry(run_number=1), key=evallog.entry_key("s1", "2026-07-02T09:00:00Z"))
    prev = evallog.parse_last_run(log.read_text(encoding="utf-8"))
    assert prev["run"] == 1
    assert prev["d1_suggestions"] == 1
    assert evallog.next_run_number(log.read_text(encoding="utf-8")) == 2


def test_comparison_arrows_reflect_prev():
    prev = {"run": 1, "misreject_num": 0.0, "d1_suggestions": 3, "d2_hits": 0}
    e = _entry(run_number=2, prev=prev)                             # this run d1_suggestions=1 < 3 → ↓
    line = [ln for ln in e.splitlines() if ln.startswith("- 对比上次")][0]
    assert "D1 建议数 ↓" in line


def test_file_lock_is_exclusive_then_reentrant_after_release(tmp_path):
    lock = tmp_path / "x.lock"
    with evallog.file_lock(lock, timeout=1.0):
        with pytest.raises(TimeoutError):
            with evallog.file_lock(lock, timeout=0.1, poll=0.01):
                pass
    with evallog.file_lock(lock, timeout=1.0):                      # released → acquirable again
        pass


def test_concurrent_appends_lose_nothing(tmp_path):
    log = tmp_path / "eval.md"
    log.write_text("# log\n", encoding="utf-8")

    def worker(i):
        sid, ts = "s%d" % i, "t%d" % i
        evallog.append_entry(log, _entry(run_number=i, session_id=sid, generated_at=ts),
                             key=evallog.entry_key(sid, ts))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    text = log.read_text(encoding="utf-8")
    assert text.count("<!-- eval-key:") == 8                        # all 8 concurrent appends survived
    assert text.startswith("# log")
