# -*- coding: utf-8 -*-
"""launcher: §12 three-layer "user-initiated" filter, §13 anti-self-consumption
guardrails, session-id resolution, and the end-to-end pipeline on a fixture."""
import builders as B
from session_export import parse, launcher, export

TS = "2026-06-18T15:00:00Z"
GEN = "2026-07-02T09:05:00Z"
RT = "2026-07-02T09:00:00Z"


# ----------------------------------------------------- §12 layer 1: trigger = human
def test_is_user_initiated_only_for_human_comment():
    assert launcher.is_user_initiated(
        {"kind": "comment", "trigger_comment_id": "c1", "author_type": "member"}) is True
    assert launcher.is_user_initiated(
        {"kind": "comment", "trigger_comment_id": "", "author_type": "member"}) is False
    assert launcher.is_user_initiated(
        {"kind": "direct", "trigger_comment_id": "c1", "author_type": "member"}) is False
    assert launcher.is_user_initiated(
        {"kind": "comment", "trigger_comment_id": "c1", "author_type": "agent"}) is False


# ----------------------------------------------------- §12 layer 2: exclude own run
def test_resolve_session_id_excludes_export_session_own_run():
    runs = [
        {"agent_id": "SELF", "kind": "comment", "completed_at": "2026-07-02T03:00:00Z",
         "result": {"session_id": "self-sid"}},
        {"agent_id": "worker", "kind": "direct", "completed_at": "2026-07-02T02:00:00Z",
         "result": {"session_id": "work-sid"}},
    ]
    assert launcher.resolve_session_id(runs, self_agent_id="SELF") == "work-sid"


def test_resolve_session_id_excludes_by_self_session_ids_and_skips_running():
    runs = [
        {"agent_id": "worker", "completed_at": None, "result": None},                 # still running
        {"agent_id": "worker", "completed_at": "t1", "result": {"session_id": "mine"}},   # self by sid
        {"agent_id": "worker", "completed_at": "t2", "result": {"session_id": "work"}},
    ]
    assert launcher.resolve_session_id(runs, self_session_ids={"mine"}) == "work"


def test_resolve_session_id_picks_latest_completed_work_run():
    runs = [
        {"agent_id": "w", "completed_at": "2026-07-02T01:00:00Z", "result": {"session_id": "old"}},
        {"agent_id": "w", "completed_at": "2026-07-02T05:00:00Z", "result": {"session_id": "new"}},
    ]
    assert launcher.resolve_session_id(runs) == "new"


def test_resolve_session_id_none_when_no_eligible():
    assert launcher.resolve_session_id([{"agent_id": "w", "result": None}]) is None


# ----------------------------------------------------- §12 layer 2: reply w/o mention
def test_build_reply_summary_has_no_mention(tmp_path):
    summ = {"session_id": "s", "title": "标题", "metrics": {"human_turns": 2},
            "frictions": [{"type": "tool_error"}]}
    text = launcher.build_reply_summary("D:\\x\\analysis.md", summ)
    assert "mention://" not in text          # no side-effecting mention link
    assert "@" not in text                    # no @mention at all (anti-loop)
    assert "analysis.md" in text


# ----------------------------------------------------- §12 layer 3 / §13: session guard
def _session(tmp_path, records, sid="guard000-0000-0000-0000-000000000000"):
    p = tmp_path / (sid + ".jsonl")
    B.write_jsonl(p, records)
    return parse.parse_session(p)


def test_session_guard_rejects_empty_session(tmp_path):
    s = _session(tmp_path, [B.ai_title("sid", "空"), B.mode("sid")])
    ok, reason = launcher.session_guard(s)
    assert ok is False and ("空" in reason or "无实质" in reason)


def test_session_guard_rejects_subagent_sidechain_session(tmp_path):
    sid = "guard000-0000-0000-0000-000000000000"
    recs = [
        {"type": "user", "isSidechain": True, "message": {"role": "user", "content": "子任务"},
         "uuid": "h1", "sessionId": sid, "timestamp": TS, "cwd": "D:\\proj"},
        {"type": "assistant", "isSidechain": True,
         "message": {"role": "assistant", "content": [{"type": "text", "text": "子代理答"}]},
         "uuid": "a1", "sessionId": sid, "timestamp": TS, "cwd": "D:\\proj"},
    ]
    ok, reason = launcher.session_guard(_session(tmp_path, recs))
    assert ok is False and "子代理" in reason        # 子代理不入扫描


def test_session_guard_rejects_self_session_id(tmp_path):
    s = _session(tmp_path, [B.human("sid", "干活", uuid="h1")])
    ok, reason = launcher.session_guard(s, self_session_ids={s.session_id})
    assert ok is False and "自身" in reason


def test_session_guard_rejects_excluded_cwd(tmp_path):
    s = _session(tmp_path, [B.human("sid", "干活", uuid="h1", cwd="D:\\jk_file\\skills\\export-session")])
    ok, reason = launcher.session_guard(s, excluded_cwd_markers=("export-session",))
    assert ok is False and "排除" in reason


def test_session_guard_accepts_normal_top_level_session(tmp_path):
    s = _session(tmp_path, [B.human("sid", "干活", uuid="h1"),
                            B.assistant("sid", [B.text("答")], uuid="a1")])
    ok, _ = launcher.session_guard(s)
    assert ok is True


# ----------------------------------------------------- end-to-end (hook path)
def _rich_session(tmp_path, wiki_doc, sid="e2e01234-0000-0000-0000-000000000000"):
    proj = tmp_path / "projects" / "D--proj"
    recs = [
        B.ai_title(sid, "端到端会话"),
        B.human(sid, "帮我查 wiki 再跑命令", uuid="h1", ts="2026-06-18T15:00:00Z"),
        B.assistant(sid, [B.tool_use("t1", "Read", {"file_path": str(wiki_doc)})],
                    uuid="a1", parent="h1", ts="2026-06-18T15:00:01Z"),
        B.tool_result(sid, "t1", "wiki 被引内容", uuid="r1", ts="2026-06-18T15:00:02Z"),
        B.assistant(sid, [B.tool_use("t2", "Bash", {"command": "x"})], uuid="a2", ts="2026-06-18T15:00:03Z"),
        B.tool_result(sid, "t2", "error: boom", uuid="r2", is_error=True, ts="2026-06-18T15:00:04Z"),
    ]
    return B.write_jsonl(proj / (sid + ".jsonl"), recs)


def _wiki(tmp_path):
    doc = tmp_path / "wiki" / "fms" / "index.md"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text("# FMS\nwiki 被引内容原文", encoding="utf-8")
    return doc


def _run(tmp_path, sub="e", **kw):
    doc = _wiki(tmp_path)
    jsonl = _rich_session(tmp_path, doc)
    return launcher.run(jsonl_path=jsonl, export_root=tmp_path / sub / "export",
                        wiki_root=str(tmp_path / "wiki"), trigger="session_end_hook",
                        exported_at=GEN, generated_at=GEN, recorded_at=RT,
                        eval_log_path=tmp_path / sub / "eval.md", **kw)


def test_end_to_end_produces_d1_d2_analysis_and_appends_evallog(tmp_path):
    res = _run(tmp_path)
    assert res["skipped"] is False
    ap = res["analysis_path"]
    assert ap.is_file()
    md = ap.read_text(encoding="utf-8")
    assert "## 3. D1" in md and "## 4. D2" in md
    assert "wiki 被引内容原文" in md               # D2 fetched the original
    assert "tool_error" in md                       # D1 picked up the friction
    # eval-log got exactly one appended run
    log = (tmp_path / "e" / "eval.md").read_text(encoding="utf-8")
    assert "· run 1 · D1+D2" in log
    assert res["eval_appended"] is True
    # index rebuilt
    assert (tmp_path / "e" / "export" / "index.json").is_file()


def test_end_to_end_analysis_is_byte_deterministic(tmp_path):
    a = _run(tmp_path, sub="a")["analysis_path"].read_bytes()
    b = _run(tmp_path, sub="b")["analysis_path"].read_bytes()
    assert a == b and not a.startswith(b"\xef\xbb\xbf")


def test_end_to_end_uses_injected_analyzer(tmp_path):
    def stub(*, summary, wiki_touches, selection_decisions):
        return {"d1_rows": [{"friction": "STUB-FRICTION", "where": "-", "attribution": "-",
                             "problem": "-", "suggestion": "-"}],
                "d2_rows": [{"touch": "STUB-TOUCH", "usage": "-", "original": "-",
                             "verdict": "幻觉", "consequence": "-", "suggestion": "-"}],
                "unselected_eval": [], "conclusions": ["STUB-CONCLUSION"]}
    md = _run(tmp_path, analyzer=stub)["analysis_path"].read_text(encoding="utf-8")
    assert "STUB-CONCLUSION" in md and "STUB-FRICTION" in md    # the controlled-analysis seam works


def test_end_to_end_skips_self_session_and_writes_auto_log(tmp_path):
    doc = _wiki(tmp_path)
    jsonl = _rich_session(tmp_path, doc)
    sid = parse.parse_session(jsonl).session_id
    res = launcher.run(jsonl_path=jsonl, export_root=tmp_path / "export",
                       wiki_root=str(tmp_path / "wiki"), trigger="session_end_hook",
                       exported_at=GEN, generated_at=GEN, recorded_at=RT,
                       eval_log_path=tmp_path / "eval.md", self_session_ids={sid})
    assert res["skipped"] is True and "自身" in res["reason"]
    assert (tmp_path / "export" / ".auto.log").is_file()        # §13.5 not silent
    assert not (tmp_path / "eval.md").is_file()                 # nothing analysed


def test_end_to_end_via_session_id_and_projects_root(tmp_path):
    doc = _wiki(tmp_path)
    _rich_session(tmp_path, doc)
    sid = "e2e01234-0000-0000-0000-000000000000"
    res = launcher.run(session_id=sid, projects_root=tmp_path / "projects",
                       export_root=tmp_path / "export", wiki_root=str(tmp_path / "wiki"),
                       trigger="comment", trigger_comment_id="c-1",
                       exported_at=GEN, generated_at=GEN, recorded_at=RT,
                       eval_log_path=tmp_path / "eval.md")
    assert res["skipped"] is False and res["analysis_path"].is_file()


# ----------------------------------------------------- SessionEnd hook payload
def test_parse_hook_payload_extracts_transcript_and_session():
    import json as _json
    payload = _json.dumps({"session_id": "sid-9", "transcript_path": "D:\\p\\sid-9.jsonl",
                           "cwd": "D:\\proj", "hook_event_name": "SessionEnd"})
    got = launcher.parse_hook_payload(payload)
    assert got["session_id"] == "sid-9"
    assert got["jsonl_path"] == "D:\\p\\sid-9.jsonl"
    assert got["cwd"] == "D:\\proj"


def test_parse_hook_payload_tolerates_missing_and_bad_json():
    empty = launcher.parse_hook_payload("{}")
    assert empty["session_id"] is None and empty["jsonl_path"] is None
    assert launcher.parse_hook_payload("not json")["session_id"] is None


# ----------------------------------------------------- CLI wiring (hook path)
def test_cli_analyze_subcommand(tmp_path):
    doc = _wiki(tmp_path)
    _rich_session(tmp_path, doc)
    sid = "e2e01234-0000-0000-0000-000000000000"
    rc = export.main(["analyze", "--session-id", sid,
                      "--projects-root", str(tmp_path / "projects"),
                      "--export-root", str(tmp_path / "export"),
                      "--wiki-root", str(tmp_path / "wiki"),
                      "--trigger", "session_end_hook",
                      "--exported-at", GEN, "--generated-at", GEN,
                      "--eval-log", str(tmp_path / "eval.md")])
    assert rc == 0
    found = list((tmp_path / "export").glob("*/analysis/*/analysis.md"))
    assert len(found) == 1
    assert "## 4. D2" in found[0].read_text(encoding="utf-8")
    assert "· run 1 · D1+D2" in (tmp_path / "eval.md").read_text(encoding="utf-8")


def test_cli_analyze_skip_returns_zero_and_logs(tmp_path):
    doc = _wiki(tmp_path)
    _rich_session(tmp_path, doc)
    sid = "e2e01234-0000-0000-0000-000000000000"
    rc = export.main(["analyze", "--session-id", sid,
                      "--projects-root", str(tmp_path / "projects"),
                      "--export-root", str(tmp_path / "export"),
                      "--wiki-root", str(tmp_path / "wiki"),
                      "--exported-at", GEN, "--generated-at", GEN,
                      "--eval-log", str(tmp_path / "eval.md"),
                      "--self-session-id", sid])          # target == self → skip
    assert rc == 0                                         # skip is a clean exit (§13.5)
    assert (tmp_path / "export" / ".auto.log").is_file()


# ----------------------------------------------------- §13.4 index write is locked
def test_concurrent_runs_same_export_root_keep_index_intact(tmp_path):
    import json
    import threading

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    eroot = tmp_path / "export"

    def one(i):
        sid = "sess%04d-0000-0000-0000-000000000000" % i
        proj = tmp_path / "projects" / "D--proj"
        B.write_jsonl(proj / (sid + ".jsonl"), [
            B.human(sid, "会话 %d" % i, uuid="h1", ts="2026-06-18T15:0%d:00Z" % i),
            B.assistant(sid, [B.text("答")], uuid="a1", ts="2026-06-18T15:0%d:01Z" % i)])
        launcher.run(jsonl_path=proj / (sid + ".jsonl"), export_root=eroot,
                     wiki_root=str(wiki), trigger="session_end_hook", exported_at=GEN,
                     generated_at=GEN, recorded_at=RT, eval_log_path=tmp_path / ("e%d.md" % i))

    threads = [threading.Thread(target=one, args=(i,)) for i in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    ix = json.loads((eroot / "index.json").read_text(encoding="utf-8"))   # valid JSON, not corrupted
    assert ix["session_count"] == 6                                        # every session indexed
