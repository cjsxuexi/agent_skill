# -*- coding: utf-8 -*-
"""render -> transcript.md: golden layout, thinking/tools, truncation->raw/, folding, subagent links."""
import builders as B
from session_export import parse, render

EXPORTED_AT = "2026-07-02T00:00:00Z"


def _render(tmp_path, sid, records, **kw):
    p = tmp_path / (sid + ".jsonl")
    B.write_jsonl(p, records)
    return render.render_transcript(parse.parse_session(p), exported_at=EXPORTED_AT, **kw)


GOLDEN_MINIMAL = """# 会话标题

> ⚠ 本导出可能含密钥 / 内部 URL,复用或外传前请自查。

- session_id: `s-golden`
- cwd: `D:\\proj`
- git: `master`
- version: `2.1.181`
- exported_at: `2026-07-02T00:00:00Z`
- 事件: 3(用户 1 / 助手 1 / 工具调用 0 / 工具结果 0);解析错误 0

## 速览

1. 你好世界

## 逐轮流水

### 👤 用户

你好世界

### 🤖 助手

回应内容
"""


def test_render_golden_minimal(tmp_path):
    md, raw = _render(tmp_path, "s-golden", [
        B.ai_title("s-golden", "会话标题"),
        B.human("s-golden", "你好世界", uuid="h1"),
        B.assistant("s-golden", [B.text("回应内容")], uuid="a1", parent="h1"),
    ])
    assert md == GOLDEN_MINIMAL
    assert raw == {}


def test_thinking_included(tmp_path):
    md, _ = _render(tmp_path, "s1", [
        B.assistant("s1", [B.thinking("内部推理"), B.text("答复")], uuid="a1")])
    assert "思考" in md and "内部推理" in md and "答复" in md


def test_tool_use_rendered_with_input(tmp_path):
    md, _ = _render(tmp_path, "s2", [
        B.assistant("s2", [B.tool_use("t1", "Read", {"file_path": "a.py"})], uuid="a1")])
    assert "**Read**" in md and "`t1`" in md and '"file_path": "a.py"' in md


def test_tool_result_error_marked(tmp_path):
    md, _ = _render(tmp_path, "s3", [
        B.assistant("s3", [B.tool_use("t1", "Bash", {})], uuid="a1"),
        B.tool_result("s3", "t1", "failed", is_error=True, uuid="r1")])
    assert "工具结果" in md and "`t1`" in md and "❌" in md and "failed" in md


def test_long_result_truncated_to_raw(tmp_path):
    big = "x" * 500
    md, raw = _render(tmp_path, "s4", [
        B.assistant("s4", [B.tool_use("t1", "Bash", {})], uuid="a1"),
        B.tool_result("s4", "t1", big, uuid="r1")], truncate_at=50)
    assert "raw/t1.txt" in md and "已截断" in md
    assert raw == {"raw/t1.txt": big}
    assert ("x" * 500) not in md            # full content is NOT inlined
    assert ("x" * 50) in md                 # first 50 chars ARE shown


def test_no_raw_disables_raw_files(tmp_path):
    big = "y" * 500
    md, raw = _render(tmp_path, "s5", [
        B.assistant("s5", [B.tool_use("t1", "Bash", {})], uuid="a1"),
        B.tool_result("s5", "t1", big, uuid="r1")], truncate_at=50, no_raw=True)
    assert raw == {}
    assert "--no-raw" in md


def test_bookkeeping_and_snapshot_excluded_from_flow(tmp_path):
    md, _ = _render(tmp_path, "s6", [
        B.mode("s6"), B.permission_mode("s6"), B.last_prompt("s6"), B.file_snapshot(),
        B.human("s6", "hi", uuid="h1")])
    assert "permission-mode" not in md and "last-prompt" not in md
    assert "file-history-snapshot" not in md and "trackedFileBackups" not in md


def test_attachment_folded_one_line(tmp_path):
    md, _ = _render(tmp_path, "s7", [
        B.attachment("s7", {"type": "hook_success", "hookName": "SessionStart:startup",
                            "content": "SECRET-CONTEXT-SHOULD-NOT-APPEAR"}, uuid="at1"),
        B.human("s7", "go", uuid="h1")])
    assert "SECRET-CONTEXT-SHOULD-NOT-APPEAR" not in md      # injected body folded away
    assert "折叠" in md


def test_subagent_link_rendered(tmp_path):
    md, _ = _render(tmp_path, "s8", [
        B.assistant("s8", [B.tool_use("t1", "Agent", {"description": "sub"})], uuid="a1")],
        subagent_links={"t1": "subagents/agent-a1f0.md"})
    assert "子代理" in md and "subagents/agent-a1f0.md" in md


def test_render_deterministic(tmp_path):
    recs = [
        B.ai_title("s9", "标题"),
        B.human("s9", "问题", uuid="h1"),
        B.assistant("s9", [B.thinking("t"), B.tool_use("t1", "Read", {"p": 1})], uuid="a1"),
        B.tool_result("s9", "t1", "z" * 300, uuid="r1"),
    ]
    a = _render(tmp_path, "s9", recs, truncate_at=50)
    b = _render(tmp_path, "s9", recs, truncate_at=50)
    assert a == b
