# -*- coding: utf-8 -*-
"""score: deterministic auto-selection by "can this complete D1/D2", recording
every unselected file + the reason **at selection time** (design §7, §2 table §1)."""
import builders as B
from session_export import parse, summarize, export, score

RT = "2026-07-02T09:00:00Z"        # recorded-at (filter time)


def _summary(tmp_path, records):
    p = tmp_path / "s.jsonl"
    B.write_jsonl(p, records)
    return summarize.summarize(parse.parse_session(p))


def test_score_session_skips_empty_session(tmp_path):
    summ = _summary(tmp_path, [B.ai_title("sid", "空"), B.mode("sid")])   # no human turns
    d = score.score_session(summ, wiki_touches=[], recorded_at=RT)
    assert d.selected is False
    assert "空会话" in d.reason or "无实质" in d.reason
    assert d.kind == "session"
    assert d.recorded_at == RT


def test_score_session_selects_substantive_session_and_reports_signals(tmp_path):
    summ = _summary(tmp_path, [
        B.human("sid", "干活", uuid="h1"),
        B.assistant("sid", [B.tool_use("t1", "Bash", {})], uuid="a1", parent="h1"),
        B.tool_result("sid", "t1", "boom", uuid="r1", is_error=True),
    ])
    d = score.score_session(summ, wiki_touches=["x"], recorded_at=RT)
    assert d.selected is True
    assert "摩擦点 1" in d.reason and "wiki 触点 1" in d.reason


def test_score_files_core_artifacts_always_selected():
    cands = [score.Candidate("transcript.md", "transcript", 10),
             score.Candidate("summary.json", "summary", 10)]
    decs = score.score_files(cands, frictions=[], wiki_touches=[], recorded_at=RT)
    assert all(d.selected for d in decs)
    assert all(d.recorded_at == RT for d in decs)


def test_score_files_subagent_dropped_without_signal_kept_with_signal():
    cand = [score.Candidate("subagents/agent-x.md", "subagent", 500)]
    dropped = score.score_files(cand, frictions=[], wiki_touches=[], recorded_at=RT)[0]
    assert dropped.selected is False and "无摩擦点" in dropped.reason
    kept = score.score_files(cand, frictions=[{"type": "tool_error"}], wiki_touches=[], recorded_at=RT)[0]
    assert kept.selected is True


def test_score_files_raw_over_budget_is_unselected_with_reason():
    cands = [score.Candidate("raw/small.txt", "raw", 100),
             score.Candidate("raw/huge.txt", "raw", 500)]
    decs = {d.path: d for d in score.score_files(cands, frictions=[], wiki_touches=[],
                                                 raw_budget=200, recorded_at=RT)}
    assert decs["raw/small.txt"].selected is True
    assert decs["raw/huge.txt"].selected is False
    assert "预算" in decs["raw/huge.txt"].reason


def test_score_files_deterministic_order_sorted_by_path():
    cands = [score.Candidate("subagents/z.md", "subagent", 1),
             score.Candidate("raw/a.txt", "raw", 1),
             score.Candidate("transcript.md", "transcript", 1)]
    paths = [d.path for d in score.score_files(cands, frictions=["f"], wiki_touches=[], recorded_at=RT)]
    assert paths == sorted(paths)


def test_candidates_from_export_reads_sizes(tmp_path):
    proj = tmp_path / "projects" / "D--proj"
    sid = "cccc1234-0000-0000-0000-000000000000"
    B.write_jsonl(proj / (sid + ".jsonl"), [
        B.human(sid, "hi", uuid="h1", ts="2026-06-18T15:00:00Z"),
        B.assistant(sid, [B.tool_use("t1", "Bash", {})], uuid="a1", ts="2026-06-18T15:00:01Z"),
        B.tool_result(sid, "t1", "L" * 5000, uuid="r1", ts="2026-06-18T15:00:02Z"),
    ])
    res = export.export_session(proj / (sid + ".jsonl"), tmp_path / "export",
                                exported_at=RT, truncate_at=100)
    cands = score.candidates_from_export(res)
    kinds = {c.kind for c in cands}
    assert "transcript" in kinds and "summary" in kinds and "raw" in kinds
    assert all(c.size_bytes > 0 for c in cands)
