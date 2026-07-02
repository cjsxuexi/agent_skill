# -*- coding: utf-8 -*-
"""score — deterministic auto-selection (design §7).

The selection standard is **"can this help complete D1 (skill/MCP effect) or D2
(wiki-usage fidelity)"**. Every decision — crucially the *unselected* ones and the
reason — is stamped with ``recorded_at`` (the filter moment) so it can be written
into ``analysis.md`` §1 *at selection time*, then judged post-hoc in §2.

Signals: substantive turns, friction count (D1), wiki-touch count (D2), and byte
size vs a raw budget. No LLM; ordering is fixed (sorted by path).
"""
from dataclasses import dataclass
from pathlib import Path

DEFAULT_RAW_BUDGET = 200_000        # bytes; a single raw/ dump above this is skipped as analysis input


@dataclass
class Candidate:
    path: str                       # display key: rel path under the export dir
    kind: str                       # transcript | summary | raw | subagent
    size_bytes: int = 0


@dataclass
class Decision:
    path: str
    selected: bool
    reason: str
    kind: str = ""                  # session | transcript | summary | raw | subagent
    recorded_at: str = ""


def score_session(summary, wiki_touches, recorded_at=""):
    """Session-level: is this session worth analysing at all?"""
    m = summary.get("metrics", {})
    human_turns = m.get("human_turns", 0)
    fc = len(summary.get("frictions", []))
    wc = len(wiki_touches or [])
    if human_turns == 0:
        reason = "空会话 / 无实质用户轮次(human_turns=0),无法完成 D1/D2,跳过"
        selected = False
    else:
        selected = True
        reason = ("有实质轮次(用户 %d);摩擦点 %d 个 → 可做 D1;wiki 触点 %d 个 → %s"
                  % (human_turns, fc, wc, "可做 D2" if wc else "D2 无触点(仅记录)"))
    return Decision(path=summary.get("session_id", ""), selected=selected,
                    reason=reason, kind="session", recorded_at=recorded_at)


def score_files(candidates, frictions, wiki_touches, raw_budget=DEFAULT_RAW_BUDGET, recorded_at=""):
    """Per-file selection for one session's export artifacts, sorted by path."""
    has_signal = bool(frictions) or bool(wiki_touches)
    decisions = []
    for c in candidates:
        if c.kind in ("transcript", "summary"):
            selected, reason = True, "核心产物,D1/D2 必需"
        elif c.kind == "subagent":
            if has_signal:
                selected, reason = True, "会话有摩擦点 / wiki 触点,子代理转写可能承载相关证据"
            else:
                selected, reason = False, "无摩擦点且无 wiki 触点,子代理转写对 D1/D2 无增量"
        elif c.kind == "raw":
            if c.size_bytes <= raw_budget:
                selected, reason = True, "截断原文在预算内(%d≤%d),保留供钻取" % (c.size_bytes, raw_budget)
            else:
                selected, reason = False, ("原始截断过大(%d>预算 %d),分析用 transcript 截断版即可"
                                           % (c.size_bytes, raw_budget))
        else:
            selected, reason = True, "未分类产物,保守保留"
        decisions.append(Decision(path=c.path, selected=selected, reason=reason,
                                  kind=c.kind, recorded_at=recorded_at))
    decisions.sort(key=lambda d: d.path)
    return decisions


def candidates_from_export(export_result):
    """Build ``Candidate`` list (with on-disk sizes) from an ``export_session`` result."""
    d = Path(export_result["export_dir"])
    cands = [
        Candidate("transcript.md", "transcript", _size(d / "transcript.md")),
        Candidate("summary.json", "summary", _size(d / "summary.json")),
    ]
    for rel in export_result.get("raw_files", []):
        cands.append(Candidate(rel, "raw", _size(d / rel)))
    for stem in export_result.get("subagents", []):
        rel = "subagents/%s.md" % stem
        cands.append(Candidate(rel, "subagent", _size(d / rel)))
    return cands


def _size(path):
    try:
        return Path(path).stat().st_size
    except OSError:
        return 0
