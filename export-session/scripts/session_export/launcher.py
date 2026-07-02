# -*- coding: utf-8 -*-
"""launcher — thin orchestration that turns a finished session into an analysis,
with the design's guardrails wired in.

Pipeline (design §4): locate session → **guardrails** → deterministic export →
score (§1 stamped at filter time) → wiki_touch → **one controlled analysis call**
(the injectable ``analyzer`` seam; default = deterministic ``baseline_judgments``)
→ render ``analysis.md`` → append the self-eval log → rebuild the index.

Guardrails:
* §12 layer 1 — :func:`is_user_initiated`: only a human comment/@mention counts.
* §12 layer 2 — :func:`resolve_session_id` excludes export-session's own runs;
  :func:`build_reply_summary` never emits an @mention (anti-loop).
* §12 layer 3 / §13 — :func:`session_guard`: top-level, substantive, not-self, cwd
  not excluded. Failures/skips go to ``<export_root>/.auto.log`` (§13.5), never silent.
"""
import json
from pathlib import Path

from . import config, parse, summarize, export, index, score, wiki_touch, analyze, evallog

EXPORT_SESSION_CWD_MARKERS = ("export-session",)
DEFAULT_EVAL_LOG = Path(__file__).resolve().parents[2] / "export-session-eval-log.md"


# ---------------------------------------------------------------- §12 layer 1
def is_user_initiated(trigger_ctx):
    """True only for a human comment/@mention run (``kind:comment`` + comment id +
    human author) — the platform-native proof of "user initiated" (design §12.1)."""
    ctx = trigger_ctx or {}
    return (ctx.get("kind") == "comment"
            and bool(ctx.get("trigger_comment_id"))
            and ctx.get("author_type") not in ("agent",))


# ---------------------------------------------------------------- §12 layer 2
def resolve_session_id(runs, self_agent_id=None, self_session_ids=()):
    """Pick the work run's ``result.session_id`` from ``multica issue runs`` JSON,
    excluding export-session's own runs (by agent id or session id) and unfinished
    runs. Ties break to the latest ``completed_at`` (design §6/§12.2)."""
    self_session_ids = set(self_session_ids or ())
    eligible = []
    for r in runs or []:
        result = r.get("result") or {}
        sid = result.get("session_id")
        if not sid:
            continue
        if self_agent_id is not None and r.get("agent_id") == self_agent_id:
            continue
        if sid in self_session_ids:
            continue
        eligible.append((r.get("completed_at") or r.get("started_at") or "", sid))
    if not eligible:
        return None
    eligible.sort(key=lambda x: x[0], reverse=True)
    return eligible[0][1]


def parse_hook_payload(text):
    """Extract ``{jsonl_path, session_id, cwd}`` from a Claude Code ``SessionEnd``
    hook stdin payload (tolerant: bad/empty JSON → all ``None``). The hook gives
    ``transcript_path`` (the jsonl) which we prefer over path re-detection."""
    try:
        obj = json.loads(text)
    except (ValueError, TypeError):
        obj = {}
    if not isinstance(obj, dict):
        obj = {}
    return {"jsonl_path": obj.get("transcript_path"),
            "session_id": obj.get("session_id"),
            "cwd": obj.get("cwd")}


def build_reply_summary(analysis_path, summary):
    """A plain-text 回贴摘要 with **no** @mention / ``mention://`` link (design §12.2)."""
    m = summary.get("metrics", {})
    return ("会话分析完成:%s。用户轮次 %d,摩擦点 %d。详见 analysis.md:%s"
            % (summary.get("title", ""), m.get("human_turns", 0),
               len(summary.get("frictions", [])), analysis_path))


# ---------------------------------------------------------------- §12 layer 3 / §13
def session_guard(session, self_session_ids=(), excluded_cwd_markers=EXPORT_SESSION_CWD_MARKERS):
    """Return ``(ok, reason)``: analyse only a top-level, substantive, non-self session
    whose cwd is not on the exclude list (design §12.3 / §13)."""
    if session.session_id in set(self_session_ids or ()):
        return False, "自身 session_id,跳过(防自噬,§12.2)"
    cwd_low = (session.cwd or "").lower()
    for marker in excluded_cwd_markers or ():
        if marker.lower() in cwd_low:
            return False, "cwd 命中排除名单(%s),跳过(§12.3)" % marker
    non_meta_human = sum(1 for e in session.events if e.kind == "human" and not e.is_meta)
    if non_meta_human == 0:
        return False, "空会话 / 无实质用户轮次,跳过(§13.2)"
    if not any(not e.is_sidechain for e in session.events):
        return False, "全部为 sidechain(子代理会话),不入扫描,跳过(§12.2)"
    return True, "ok"


def append_auto_log(export_root, message):
    """Append a line to ``<export_root>/.auto.log`` — never swallow errors (§13.5)."""
    log = Path(export_root) / ".auto.log"
    existing = config.read_text(log) if log.is_file() else ""
    config.write_text(log, existing + message + "\n")


# ---------------------------------------------------------------- orchestration
def _locate(jsonl_path, session_id, projects_root):
    if jsonl_path:
        return Path(jsonl_path)
    if session_id and projects_root:
        return export.locate_session(projects_root, session_id)
    raise ValueError("run() needs jsonl_path or (session_id and projects_root)")


def _health(summary, duration="-"):
    pe = summary.get("metrics", {}).get("parse_errors", 0)
    return {"attribution": "中(基线归因;可经受控分析细化)",
            "recursion": "无", "timeout": "无",
            "parse_errors": "无" if not pe else "有(%d)" % pe,
            "duration": duration, "scale": "%d 条事件" % summary.get("metrics", {}).get("total_events", 0),
            "d2_page_specific": "否(基线待深判)", "routed": "否"}


def run(*, jsonl_path=None, session_id=None, projects_root=None, export_root,
        wiki_root=config.DEFAULT_WIKI_ROOT, trigger, trigger_comment_id="",
        exported_at="", generated_at="", recorded_at="", no_raw=False,
        truncate_at=export.DEFAULT_TRUNCATE_AT, self_session_ids=(),
        excluded_cwd_markers=EXPORT_SESSION_CWD_MARKERS,
        analyzer=analyze.baseline_judgments, eval_log_path=None):
    """Run the full analyze pipeline for one session. Returns a result dict; on a
    guardrail skip returns ``{"skipped": True, "reason": ...}`` (and logs it)."""
    generated_at = generated_at or exported_at
    recorded_at = recorded_at or generated_at
    eval_log_path = Path(eval_log_path) if eval_log_path else DEFAULT_EVAL_LOG
    jsonl = _locate(jsonl_path, session_id, projects_root)

    session = parse.parse_session(jsonl)
    ok, reason = session_guard(session, self_session_ids=self_session_ids,
                               excluded_cwd_markers=excluded_cwd_markers)
    if not ok:
        append_auto_log(export_root, "[skip] %s session=%s :: %s"
                        % (generated_at, session.session_id, reason))
        return {"skipped": True, "reason": reason, "session_id": session.session_id}

    # deterministic export + signals
    export_result = export.export_session(jsonl, export_root, exported_at=exported_at,
                                          no_raw=no_raw, truncate_at=truncate_at)
    summary = summarize.summarize(session, exported_at=exported_at)
    touches = wiki_touch.detect_wiki_touches(session, wiki_root=wiki_root)

    # score — §1 rows stamped with recorded_at (the filter moment)
    session_decision = score.score_session(summary, touches, recorded_at=recorded_at)
    candidates = score.candidates_from_export(export_result)
    file_decisions = score.score_files(candidates, summary["frictions"], touches,
                                       recorded_at=recorded_at)
    selection_decisions = [session_decision] + file_decisions

    # one controlled analysis call (injectable; default deterministic baseline)
    judgments = analyzer(summary=summary, wiki_touches=touches,
                         selection_decisions=selection_decisions)

    first_ts = summary.get("first_timestamp") or generated_at
    date = first_ts[:10] if first_ts else generated_at[:10]
    md = analyze.render_analysis_md(
        session_id=session.session_id, source_jsonl=str(jsonl), trigger=trigger,
        trigger_comment_id=trigger_comment_id, wiki_root=wiki_root,
        generated_at=generated_at, date=date,
        selection_decisions=selection_decisions, judgments=judgments)

    slug = config.slugify(generated_at + "_D1D2", maxlen=60)
    analysis_dir = Path(export_result["export_dir"]) / "analysis" / slug
    analysis_path = config.write_text(analysis_dir / "analysis.md", md)

    # self-eval log (idempotent + locked)
    stats = analyze.judgment_stats(judgments, selection_decisions)
    log_text = config.read_text(eval_log_path) if Path(eval_log_path).is_file() else ""
    run_number = evallog.next_run_number(log_text)
    prev = evallog.parse_last_run(log_text)
    entry = evallog.build_entry(
        run_number=run_number, generated_at=generated_at, trigger=trigger,
        session_id=session.session_id, stats=stats, health=_health(summary),
        conclusion="run %d:%d 摩擦点 / %d wiki 触点;详见 analysis.md" % (
            run_number, stats["d1_problems"], stats["d2_total"]),
        next_suggestion="按 §2 误退率与 D2 低置信比例调打分阈值 / 补 fixture(§7/§8)", prev=prev)
    eval_appended = evallog.append_entry(
        eval_log_path, entry, key=evallog.entry_key(session.session_id, generated_at))

    # rebuild cross-session index — locked so concurrent triggers on the same
    # export_root serialise their INDEX/index.json writes (design §13.4)
    with evallog.file_lock(Path(export_root) / ".index.lock"):
        index.build_index(export_root, exported_at=exported_at)

    return {
        "skipped": False,
        "session_id": session.session_id,
        "export_dir": Path(export_result["export_dir"]),
        "analysis_path": analysis_path,
        "eval_log_path": Path(eval_log_path),
        "eval_appended": eval_appended,
        "run_number": run_number,
        "selection_decisions": selection_decisions,
        "wiki_touches": touches,
        "reply_summary": build_reply_summary(analysis_path, summary),
    }
