# -*- coding: utf-8 -*-
"""analyze — render ``analysis.md`` from the fixed template + a deterministic
baseline analyzer (design §8, template ``references/analysis-template.md``).

Two concerns, kept separate so the pipeline stays testable:

* ``render_analysis_md`` — pure formatter. Given the selection decisions (§1, each
  stamped at *filter time*) and a ``judgments`` payload (§2 backfill, §3 D1, §4 D2,
  §5 conclusions), it emits the template byte-deterministically.
* ``baseline_judgments`` — the default, zero-LLM analyzer. It turns deterministic
  signals into a valid, conservative ``judgments`` payload: D1 rows from frictions;
  D2 rows from wiki touchpoints (with the fetched original attached, and a
  **低置信疑似** verdict whenever no exact original was reachable — design §17.2).
  The deep judgment (hallucination / misread) is where a real *controlled analysis*
  call (an LLM, or the agent itself) refines these rows; the seam is the ``analyzer``
  argument in :mod:`session_export.launcher`.
"""
FRICTION_ATTRIBUTION = {
    "tool_error": ("工具调用报错", "该工具在此上下文下易失败", "复核参数 / 加前置校验或重试"),
    "retry": ("同一工具失败后重试", "首调用失败触发重试,存在无效往返", "定位首调用失败根因,减少重试"),
    "permission_denied": ("权限被拒", "所需权限未预先授予", "在 settings 预授权或改用已授权路径"),
    "user_correction": ("用户纠正 agent", "agent 产出偏离用户意图", "复盘该轮理解偏差,补 skill/提示约束"),
}
LOW_CONF = "低置信疑似"


def _cell(text):
    """Table-cell-safe: escape ``|``, flatten newlines (mirrors index._cell)."""
    return str("" if text is None else text).replace("|", "\\|").replace("\n", " ").strip()


# ---------------------------------------------------------------- baseline analyzer
def baseline_judgments(*, summary, wiki_touches, selection_decisions):
    """Deterministic default analyzer → a ``judgments`` payload (no LLM)."""
    return {
        "d1_rows": _baseline_d1(summary.get("frictions", [])),
        "d2_rows": _baseline_d2(wiki_touches or []),
        "unselected_eval": _baseline_unselected(selection_decisions),
        "conclusions": _baseline_conclusions(summary, wiki_touches or []),
    }


def _baseline_d1(frictions):
    if not frictions:
        return [{"friction": "(无摩擦点)", "where": "-", "attribution": "本会话 skill/MCP 运行顺畅",
                 "problem": "无", "suggestion": "无"}]
    rows = []
    for f in frictions:
        attr, problem, suggestion = FRICTION_ATTRIBUTION.get(
            f.get("type", ""), ("其它摩擦", "见 detail", "人工复核"))
        where = "轮次≈%s / 工具 %s" % (f.get("index", "?"), f.get("tool") or "-")
        rows.append({"friction": "%s:%s" % (f.get("type", ""), f.get("detail", "")),
                     "where": where, "attribution": attr, "problem": problem,
                     "suggestion": suggestion})
    return rows


def _baseline_d2(wiki_touches):
    if not wiki_touches:
        return [{"touch": "(无 wiki 触点)", "usage": "-", "original": "-",
                 "verdict": "不适用", "consequence": "-", "suggestion": "-"}]
    rows = []
    for t in wiki_touches:
        has_original = t.quoted_original is not None
        rows.append({
            "touch": "%s · %s" % (t.kind, t.ref),
            "usage": "见 transcript 事件 #%d(%s)" % (t.index, t.tool),
            "original": t.quoted_original if has_original else "(未取到确切被引原文)",
            "verdict": "待判定(原文已附,需 LLM/人工比对)" if has_original else LOW_CONF,
            "consequence": "待判定",
            "suggestion": "待判定;wiki 类建议交 /wiki-refine",
        })
    return rows


def _baseline_unselected(selection_decisions):
    """Baseline defaults every unselected item to 合理 (it *is* the decider); a real
    analyzer may flip one to 误退 in §2."""
    rows = []
    for d in selection_decisions:
        if not d.selected:
            rows.append({"path": d.path, "orig_reason": d.reason,
                         "verdict": "合理(基线默认;可人工/LLM 复核)",
                         "impact": "无(基线判定未选合理)"})
    return rows


def _baseline_conclusions(summary, wiki_touches):
    fc = len(summary.get("frictions", []))
    wc = len(wiki_touches)
    high = sum(1 for t in wiki_touches if t.quoted_original is not None)
    return [
        "D1:发现 %d 个摩擦点%s" % (fc, ",逐条见 §3;无摩擦点表示运行顺畅" if fc else "(运行顺畅)"),
        "D2:%d 个 wiki 触点,其中 %d 个取到原文可比对、%d 个低置信疑似(§17.2)" % (wc, high, wc - high),
        "全部为建议,人拍板;wiki 类建议交 /wiki-refine。",
    ]


def judgment_stats(judgments, selection_decisions):
    """Roll a ``judgments`` payload into the counts the eval-log entry needs."""
    selected = sum(1 for d in selection_decisions if d.selected)
    unselected = sum(1 for d in selection_decisions if not d.selected)
    misrejected = sum(1 for r in judgments["unselected_eval"] if "误退" in r.get("verdict", ""))
    d1_real = [r for r in judgments["d1_rows"] if r.get("problem") not in ("无", "", None)]
    d2 = judgments["d2_rows"]
    return {
        "selected": selected,
        "unselected": unselected,
        "misrejected": misrejected,
        "misreject_rate": "%d/%d" % (misrejected, unselected),
        "d1_problems": len(d1_real),
        "d1_suggestions": sum(1 for r in d1_real if r.get("suggestion") not in ("无", "", None)),
        "d2_total": 0 if (len(d2) == 1 and d2[0]["verdict"] == "不适用") else len(d2),
        "d2_hallucination": sum(1 for r in d2 if "幻觉" in r["verdict"]),
        "d2_misread": sum(1 for r in d2 if "误解" in r["verdict"]),
        "d2_incomplete": sum(1 for r in d2 if "不完整" in r["verdict"]),
        "d2_inaccurate": sum(1 for r in d2 if "不准确" in r["verdict"]),
        "d2_low_confidence": sum(1 for r in d2 if r["verdict"] == LOW_CONF),
    }


# ---------------------------------------------------------------- renderer
def render_analysis_md(*, session_id, source_jsonl, trigger, trigger_comment_id,
                       wiki_root, generated_at, date, selection_decisions, judgments):
    """Render the full ``analysis.md`` (template_version 3), byte-deterministic."""
    L = []
    L.append("---")
    L.append("schema_version: 1")
    L.append("template_version: 3")
    L.append("analysis_goals: [skill_mcp_effectiveness, wiki_usage_fidelity]")
    L.append("session_id: %s" % session_id)
    L.append("source_jsonl: %s" % source_jsonl)
    L.append("trigger: %s" % trigger)
    L.append("trigger_comment_id: %s" % (trigger_comment_id or "-"))
    L.append("wiki_root: %s" % wiki_root)
    L.append("generated_at: %s" % generated_at)
    L.append("---")
    L.append("")
    L.append("# 会话分析报告 — (%s)" % date)
    L.append("")
    L.append("> ⚠ 本文件可能含密钥 / 内部 URL,复用或外传前请自查。")
    L.append("> 本报告仅为**发现 + 建议**;是否改、如何改由人拍板。wiki 修订走 /wiki-refine。")
    L.append("")

    L.append("## 1. 选择决策(筛选阶段实时写)")
    L.append("")
    L.append("| 文件 / 会话 | 选中? | 理由 | 记录时刻 |")
    L.append("| -- | -- | -- | -- |")
    for d in selection_decisions:
        L.append("| %s | %s | %s | %s |" % (
            _cell(d.path), "是" if d.selected else "否", _cell(d.reason), _cell(d.recorded_at)))
    L.append("")

    L.append("## 2. 未选项事后评估(产出时回填)")
    L.append("")
    L.append("| 未选文件 | 当时不选理由 | 事后评估(合理 / 误退) | 若应补选的影响 |")
    L.append("| -- | -- | -- | -- |")
    if judgments["unselected_eval"]:
        for r in judgments["unselected_eval"]:
            L.append("| %s | %s | %s | %s |" % (
                _cell(r["path"]), _cell(r["orig_reason"]), _cell(r["verdict"]), _cell(r["impact"])))
    else:
        L.append("| (无未选项) | - | - | - |")
    L.append("")

    L.append("## 3. D1 · skill/MCP 运行效果")
    L.append("")
    L.append("| 摩擦点 | 位置(轮次/工具) | 归因 | 问题(可监控) | 改造建议(可执行) |")
    L.append("| -- | -- | -- | -- | -- |")
    for r in judgments["d1_rows"]:
        L.append("| %s | %s | %s | %s | %s |" % (
            _cell(r["friction"]), _cell(r["where"]), _cell(r["attribution"]),
            _cell(r["problem"]), _cell(r["suggestion"])))
    L.append("")

    L.append("## 4. D2 · 本会话 wiki 使用保真度")
    L.append("")
    L.append("判定 ∈ {正确, 幻觉, 误解, wiki 不完整致跑偏, wiki 不准确致跑偏, **低置信疑似**}。"
             "无确切被引原文(凭记忆用 wiki)→ 标\"低置信疑似\",不硬判幻觉(设计 §17.2)。")
    L.append("")
    L.append("| wiki 触点 | agent 当时如何使用/理解 | 比对被引原文 | 判定 | 后果 | wiki 改进建议(交 /wiki-refine) |")
    L.append("| -- | -- | -- | -- | -- | -- |")
    for r in judgments["d2_rows"]:
        L.append("| %s | %s | %s | %s | %s | %s |" % (
            _cell(r["touch"]), _cell(r["usage"]), _cell(r["original"]),
            _cell(r["verdict"]), _cell(r["consequence"]), _cell(r["suggestion"])))
    L.append("")

    L.append("## 5. 结论与建议(D1 + D2 汇总,按优先级)")
    L.append("")
    L.append("> 全部为**建议**,人拍板;wiki 类建议交 /wiki-refine。")
    L.append("")
    for i, c in enumerate(judgments["conclusions"], 1):
        L.append("%d. %s" % (i, c))
    L.append("")

    L.append("## 6. 与历史对比摘要")
    L.append("")
    L.append("- 详见自评记录:`D:\\jk_file\\skills\\export-session\\export-session-eval-log.md` 本次条目"
             "(本次 vs 历次:误退率、D1 问题/建议数、D2 各判定处数、流程健康)。")
    return "\n".join(L) + "\n"
