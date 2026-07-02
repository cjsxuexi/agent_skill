# -*- coding: utf-8 -*-
"""analyze: render analysis.md from the fixed template (§1 at filter time, §2 at
production time, D1 + D2), plus a deterministic baseline analyzer (design §8/§17.2)."""
from session_export import analyze, score, wiki_touch

RT = "2026-07-02T09:00:00Z"        # recorded-at (filter time)
GEN = "2026-07-02T09:05:00Z"       # generated-at (production time)


def _decisions():
    return [
        score.Decision("sid", True, "有实质轮次", kind="session", recorded_at=RT),
        score.Decision("transcript.md", True, "核心产物,D1/D2 必需", kind="transcript", recorded_at=RT),
        score.Decision("raw/huge.txt", False, "原始截断过大,分析用截断版即可", kind="raw", recorded_at=RT),
    ]


def _render(judgments, decisions=None):
    return analyze.render_analysis_md(
        session_id="sid-1", source_jsonl="~/.claude/projects/x/sid-1.jsonl",
        trigger="comment", trigger_comment_id="c-42", wiki_root="D:\\wiki",
        generated_at=GEN, date="2026-07-02",
        selection_decisions=decisions or _decisions(), judgments=judgments)


def test_render_has_frontmatter_and_all_six_sections():
    md = _render(analyze.baseline_judgments(summary=_min_summary(), wiki_touches=[],
                                            selection_decisions=_decisions()))
    assert "schema_version: 1" in md and "template_version: 3" in md
    assert "session_id: sid-1" in md and "trigger: comment" in md
    assert "trigger_comment_id: c-42" in md and ("generated_at: " + GEN) in md
    for header in ("## 1. 选择决策", "## 2. 未选项事后评估", "## 3. D1",
                   "## 4. D2", "## 5. 结论与建议", "## 6. 与历史对比"):
        assert header in md, "missing section: " + header


def test_section1_uses_recorded_at_not_generated_at():
    md = _render(analyze.baseline_judgments(summary=_min_summary(), wiki_touches=[],
                                            selection_decisions=_decisions()))
    sec1 = md.split("## 1. 选择决策")[1].split("## 2.")[0]   # the §1 table only
    assert RT in sec1                      # §1 rows carry the filter-time stamp
    assert GEN not in sec1                 # not the production-time stamp
    assert "raw/huge.txt" in sec1 and "原始截断过大" in sec1   # unselected file + reason at selection time


def test_baseline_d1_rows_from_frictions():
    summ = _min_summary(frictions=[
        {"type": "tool_error", "index": 3, "tool": "Bash", "detail": "boom"},
        {"type": "user_correction", "index": 7, "tool": "", "detail": "不对,重来"},
    ])
    j = analyze.baseline_judgments(summary=summ, wiki_touches=[], selection_decisions=_decisions())
    assert len(j["d1_rows"]) == 2
    assert any("tool_error" in r["friction"] for r in j["d1_rows"])


def test_baseline_d2_low_confidence_without_original_high_with_original():
    touches = [
        wiki_touch.WikiTouch(kind="read_wiki_file", tool="Read", index=1, ref="D:\\wiki\\a.md",
                             quoted_original="原文段落", confidence="high"),
        wiki_touch.WikiTouch(kind="ones_wiki_mcp", tool="mcp__ones_wiki__x", index=2, ref="page=1",
                             quoted_original=None, confidence="low"),
    ]
    j = analyze.baseline_judgments(summary=_min_summary(), wiki_touches=touches,
                                   selection_decisions=_decisions())
    verdicts = [r["verdict"] for r in j["d2_rows"]]
    assert "低置信疑似" in verdicts                # the mcp touch, no fetched original (§17.2)
    assert any(v != "低置信疑似" for v in verdicts)  # the read touch, original attached


def test_baseline_unselected_eval_covers_every_unselected():
    j = analyze.baseline_judgments(summary=_min_summary(), wiki_touches=[],
                                   selection_decisions=_decisions())
    paths = [r["path"] for r in j["unselected_eval"]]
    assert paths == ["raw/huge.txt"]              # only the one unselected file
    assert "原始截断过大" in j["unselected_eval"][0]["orig_reason"]


def test_judgment_stats_counts():
    touches = [
        wiki_touch.WikiTouch("read_wiki_file", "Read", 1, "a", quoted_original="x", confidence="high"),
        wiki_touch.WikiTouch("ones_wiki_mcp", "m", 2, "b", quoted_original=None, confidence="low"),
    ]
    summ = _min_summary(frictions=[{"type": "tool_error", "index": 1, "tool": "Bash", "detail": "d"}])
    j = analyze.baseline_judgments(summary=summ, wiki_touches=touches, selection_decisions=_decisions())
    st = analyze.judgment_stats(j, _decisions())
    assert st["selected"] == 2 and st["unselected"] == 1
    assert st["misrejected"] == 0 and st["misreject_rate"] == "0/1"
    assert st["d1_problems"] == 1
    assert st["d2_low_confidence"] == 1


def test_render_is_deterministic():
    j = analyze.baseline_judgments(summary=_min_summary(), wiki_touches=[],
                                   selection_decisions=_decisions())
    assert _render(j) == _render(j)


def _min_summary(frictions=None):
    return {
        "session_id": "sid-1",
        "title": "标题",
        "metrics": {"human_turns": 2, "assistant_turns": 2, "tool_calls": 1,
                    "tool_errors": 0, "total_events": 5, "parse_errors": 0},
        "frictions": frictions or [],
    }
