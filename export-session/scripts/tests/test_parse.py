# -*- coding: utf-8 -*-
"""Parser: classify every jsonl line/block type; title derivation; fault tolerance."""
import builders as B
from session_export import parse


def test_parse_basic_flow(tmp_path):
    sid = "11111111-1111-1111-1111-111111111111"
    p = tmp_path / (sid + ".jsonl")
    B.write_jsonl(p, [
        B.ai_title(sid, "修复登录重定向"),
        B.mode(sid), B.permission_mode(sid),
        B.human(sid, "帮我修复登录", uuid="h1"),
        B.assistant(sid, [B.thinking("先看代码"), B.text("好的"),
                          B.tool_use("t1", "Read", {"file_path": "a.py"})], uuid="a1", parent="h1"),
        B.tool_result(sid, "t1", "file contents", uuid="r1", parent="a1"),
    ])
    s = parse.parse_session(p)
    assert s.session_id == sid
    assert s.title == "修复登录重定向"
    assert s.ai_title == "修复登录重定向"
    kinds = [e.kind for e in s.events]
    assert kinds == ["bookkeeping", "bookkeeping", "bookkeeping", "human", "assistant", "tool_result"]
    a = s.events[4]
    assert [b.kind for b in a.blocks] == ["thinking", "text", "tool_use"]
    assert a.blocks[2].name == "Read"
    assert a.blocks[2].tool_id == "t1"
    assert a.blocks[2].tool_input == {"file_path": "a.py"}
    tr = s.events[5]
    assert tr.kind == "tool_result" and tr.tool_id == "t1" and tr.is_error is False
    assert tr.blocks[0].text == "file contents"


def test_all_bookkeeping_types_classified(tmp_path):
    sid = "22222222-2222-2222-2222-222222222222"
    p = tmp_path / (sid + ".jsonl")
    B.write_jsonl(p, [
        B.mode(sid), B.permission_mode(sid), B.last_prompt(sid),
        B.file_snapshot(), B.ai_title(sid, "t"),
    ])
    s = parse.parse_session(p)
    assert all(e.kind == "bookkeeping" for e in s.events)
    assert {e.subtype for e in s.events} == {
        "mode", "permission-mode", "last-prompt", "file-history-snapshot", "ai-title"}


def test_title_falls_back_to_first_human_prompt(tmp_path):
    sid = "33333333-3333-3333-3333-333333333333"
    p = tmp_path / (sid + ".jsonl")
    B.write_jsonl(p, [
        B.human(sid, "第一句话\n第二行不要", uuid="h1"),
        B.assistant(sid, [B.text("ok")], uuid="a1", parent="h1"),
    ])
    s = parse.parse_session(p)
    assert s.ai_title == ""
    assert s.title == "第一句话"          # first line only, ai-title fallback (design §14)


def test_title_falls_back_to_session_id_when_no_prompt(tmp_path):
    sid = "44444444-4444-4444-4444-444444444444"
    p = tmp_path / (sid + ".jsonl")
    B.write_jsonl(p, [B.assistant(sid, [B.text("hi")], uuid="a1")])
    s = parse.parse_session(p)
    assert s.title == sid


def test_empty_session(tmp_path):
    sid = "55555555-5555-5555-5555-555555555555"
    p = tmp_path / (sid + ".jsonl")
    B.write_jsonl(p, [])
    s = parse.parse_session(p)
    assert s.events == []
    assert s.session_id == sid
    assert s.title == sid
    assert s.parse_errors == 0


def test_tolerates_malformed_trailing_line(tmp_path):
    """§13.3 尾部未落盘: a truncated final half-line must not crash the parser."""
    sid = "66666666-6666-6666-6666-666666666666"
    p = tmp_path / (sid + ".jsonl")
    B.write_jsonl(p, [
        B.human(sid, "hello", uuid="h1"),
        '{"type":"assistant","message":{"role":"assistant","content":[{"type":"te',  # truncated
    ])
    s = parse.parse_session(p)
    assert [e.kind for e in s.events] == ["human"]
    assert s.parse_errors == 1


def test_tool_result_error_flag(tmp_path):
    sid = "77777777-7777-7777-7777-777777777777"
    p = tmp_path / (sid + ".jsonl")
    B.write_jsonl(p, [B.tool_result(sid, "t9", "boom", is_error=True, uuid="r1")])
    tr = parse.parse_session(p).events[0]
    assert tr.kind == "tool_result" and tr.is_error is True
    assert tr.blocks[0].is_error is True


def test_tool_result_list_content_joined(tmp_path):
    sid = "88888888-8888-8888-8888-888888888888"
    p = tmp_path / (sid + ".jsonl")
    B.write_jsonl(p, [B.tool_result(
        sid, "t1", [{"type": "text", "text": "line A"}, {"type": "text", "text": "line B"}], uuid="r1")])
    tr = parse.parse_session(p).events[0]
    assert tr.blocks[0].text == "line A\nline B"


def test_ai_title_last_wins(tmp_path):
    sid = "99999999-9999-9999-9999-999999999999"
    p = tmp_path / (sid + ".jsonl")
    B.write_jsonl(p, [B.ai_title(sid, "旧标题"), B.human(sid, "x", uuid="h1"), B.ai_title(sid, "新标题")])
    assert parse.parse_session(p).title == "新标题"


def test_meta_human_flagged(tmp_path):
    sid = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    p = tmp_path / (sid + ".jsonl")
    B.write_jsonl(p, [B.human(sid, "<caveat>local command</caveat>", uuid="m1", is_meta=True)])
    e = parse.parse_session(p).events[0]
    assert e.kind == "human" and e.is_meta is True


def test_sidechain_flag_preserved(tmp_path):
    sid = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    p = tmp_path / (sid + ".jsonl")
    B.write_jsonl(p, [B.assistant(sid, [B.text("sub")], uuid="a1", is_sidechain=True)])
    assert parse.parse_session(p).events[0].is_sidechain is True


def test_tolerates_workflow_journal_lines(tmp_path):
    """Workflow journals use a different started/result schema; the parser must
    tolerate them (classify as bookkeeping, never crash). Full workflow transcript
    rendering is deferred to Stage 2 — here we only assert graceful ingestion."""
    sid = "dddddddd-dddd-dddd-dddd-dddddddddddd"
    p = tmp_path / (sid + ".jsonl")
    B.write_jsonl(p, [
        {"type": "started", "key": "v2:abc", "agentId": "a80376e2cc21e0582"},
        {"type": "result", "key": "v2:abc", "agentId": "a80376e2cc21e0582",
         "result": {"findings": [], "overall": "clean"}},
    ])
    s = parse.parse_session(p)
    assert s.parse_errors == 0
    assert [e.kind for e in s.events] == ["bookkeeping", "bookkeeping"]
    assert {e.subtype for e in s.events} == {"started", "result"}


def test_attachment_and_system_classified(tmp_path):
    sid = "cccccccc-cccc-cccc-cccc-cccccccccccc"
    p = tmp_path / (sid + ".jsonl")
    B.write_jsonl(p, [
        B.attachment(sid, {"type": "hook_success", "hookName": "SessionStart:startup", "content": "x"}, uuid="at1"),
        B.system(sid, subtype="turn_duration", uuid="sy1", duration_ms=1234),
    ])
    s = parse.parse_session(p)
    assert s.events[0].kind == "attachment" and s.events[0].subtype == "hook_success"
    assert s.events[1].kind == "system" and s.events[1].subtype == "turn_duration"
