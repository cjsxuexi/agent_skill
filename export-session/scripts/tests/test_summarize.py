# -*- coding: utf-8 -*-
"""§10 summary.json: metrics, tool usage, deterministic friction extraction."""
import builders as B
from session_export import parse, summarize


def _summ(tmp_path, sid, records, exported_at="2026-07-02T00:00:00Z"):
    p = tmp_path / (sid + ".jsonl")
    B.write_jsonl(p, records)
    return summarize.summarize(parse.parse_session(p), exported_at=exported_at)


def test_metrics_and_tool_usage(tmp_path):
    sid = "s-metrics"
    d = _summ(tmp_path, sid, [
        B.ai_title(sid, "t"), B.mode(sid),
        B.human(sid, "帮我修复登录", uuid="h1"),
        B.assistant(sid, [B.thinking("x"), B.text("ok"), B.tool_use("t1", "Read", {})], uuid="a1"),
        B.tool_result(sid, "t1", "ok", uuid="r1"),
        B.assistant(sid, [B.tool_use("t2", "Bash", {})], uuid="a2"),
        B.tool_result(sid, "t2", "boom", is_error=True, uuid="r2"),
        B.human(sid, "不对,重来", uuid="h2"),
    ])
    m = d["metrics"]
    assert m["human_turns"] == 2
    assert m["assistant_turns"] == 2
    assert m["tool_calls"] == 2
    assert m["tool_results"] == 2
    assert m["tool_errors"] == 1
    assert m["thinking_blocks"] == 1
    assert m["bookkeeping_lines"] == 2
    assert m["total_events"] == 8
    assert d["tool_usage"] == {"Bash": 1, "Read": 1}
    assert d["session_id"] == sid and d["exported_at"] == "2026-07-02T00:00:00Z"


def test_friction_tool_error_names_the_tool(tmp_path):
    sid = "s-err"
    d = _summ(tmp_path, sid, [
        B.assistant(sid, [B.tool_use("t1", "Bash", {})], uuid="a1"),
        B.tool_result(sid, "t1", "command failed", is_error=True, uuid="r1"),
    ])
    fr = d["frictions"]
    assert len(fr) == 1
    assert fr[0]["type"] == "tool_error" and fr[0]["tool"] == "Bash"


def test_friction_permission_denied(tmp_path):
    sid = "s-perm"
    d = _summ(tmp_path, sid, [
        B.assistant(sid, [B.tool_use("t1", "Bash", {})], uuid="a1"),
        B.tool_result(sid, "t1", "The user has not granted permission to use Bash", is_error=True, uuid="r1"),
    ])
    fr = d["frictions"]
    assert len(fr) == 1 and fr[0]["type"] == "permission_denied"


def test_friction_user_correction(tmp_path):
    sid = "s-corr"
    d = _summ(tmp_path, sid, [
        B.assistant(sid, [B.text("done")], uuid="a1"),
        B.human(sid, "不对,这不是我要的", uuid="h2"),
    ])
    types = [f["type"] for f in d["frictions"]]
    assert "user_correction" in types


def test_friction_retry_same_tool_after_error(tmp_path):
    sid = "s-retry"
    d = _summ(tmp_path, sid, [
        B.assistant(sid, [B.tool_use("t1", "Bash", {})], uuid="a1"),
        B.tool_result(sid, "t1", "err", is_error=True, uuid="r1"),
        B.assistant(sid, [B.tool_use("t2", "Bash", {})], uuid="a2"),
        B.tool_result(sid, "t2", "ok", uuid="r2"),
    ])
    types = [f["type"] for f in d["frictions"]]
    assert "retry" in types


def test_frictions_sorted_by_index(tmp_path):
    sid = "s-sort"
    d = _summ(tmp_path, sid, [
        B.assistant(sid, [B.tool_use("t1", "Bash", {})], uuid="a1"),
        B.tool_result(sid, "t1", "err", is_error=True, uuid="r1"),
        B.human(sid, "错了", uuid="h2"),
    ])
    idxs = [f["index"] for f in d["frictions"]]
    assert idxs == sorted(idxs)


def test_empty_session_summary(tmp_path):
    sid = "s-empty"
    d = _summ(tmp_path, sid, [])
    assert d["frictions"] == []
    assert d["metrics"]["total_events"] == 0
    assert d["tool_usage"] == {}


def test_summary_is_deterministic(tmp_path):
    sid = "s-det"
    recs = [
        B.assistant(sid, [B.tool_use("t1", "Read", {})], uuid="a1"),
        B.tool_result(sid, "t1", "x", uuid="r1"),
    ]
    a = _summ(tmp_path, sid, recs)
    b = _summ(tmp_path, sid, recs)
    assert a == b
