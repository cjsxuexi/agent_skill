# -*- coding: utf-8 -*-
"""render -> ``transcript.md`` (design §10).

Pure & deterministic: returns ``(markdown, raw_files)`` where ``raw_files`` maps
``raw/<id>.txt`` -> full content for over-long results the orchestrator writes.
Bookkeeping rows are dropped from the flow; injected/attachment/meta/system rows
fold to a single line; sub-agent tool calls get a recursive link.
"""
from . import config

WARN = "> ⚠ 本导出可能含密钥 / 内部 URL,复用或外传前请自查。"
DEFAULT_TRUNCATE_AT = 2000


def _fence(body, lang=""):
    return "```%s\n%s\n```" % (lang, body)


def _blockquote(text, prefix="> "):
    lines = text.split("\n")
    return "\n".join(prefix + ln if ln else prefix.rstrip() for ln in lines)


def render_transcript(session, exported_at="", no_raw=False,
                      truncate_at=DEFAULT_TRUNCATE_AT, subagent_links=None):
    subagent_links = subagent_links or {}
    raw_files = {}
    sections = []

    # ---- header ----
    h = a = tc = tr = 0
    prompts = []
    for e in session.events:
        if e.kind == "human" and not e.is_meta:
            h += 1
            prompts.append(e.text)
        elif e.kind == "assistant":
            a += 1
            tc += sum(1 for b in e.blocks if b.kind == "tool_use")
        elif e.kind == "tool_result":
            tr += 1

    sections.append("# " + session.title)
    sections.append(WARN)
    sections.append("\n".join([
        "- session_id: `%s`" % session.session_id,
        "- cwd: `%s`" % session.cwd,
        "- git: `%s`" % session.git_branch,
        "- version: `%s`" % session.version,
        "- exported_at: `%s`" % exported_at,
        "- 事件: %d(用户 %d / 助手 %d / 工具调用 %d / 工具结果 %d);解析错误 %d" % (
            len(session.events), h, a, tc, tr, session.parse_errors),
    ]))

    # ---- 速览 ----
    sections.append("## 速览")
    if prompts:
        outline = []
        for i, pt in enumerate(prompts, 1):
            first = (pt.strip().splitlines() or [""])[0].strip()
            outline.append("%d. %s" % (i, first[:100]))
        sections.append("\n".join(outline))
    else:
        sections.append("_(无用户消息)_")

    # ---- 逐轮流水 ----
    sections.append("## 逐轮流水")
    for e in session.events:
        if e.kind == "bookkeeping":
            continue
        if e.kind == "attachment":
            sections.append("_(注入内容已折叠:%s)_" % (e.subtype or "attachment"))
        elif e.kind == "system":
            sections.append("_(系统事件已折叠:%s)_" % (e.subtype or "system"))
        elif e.kind == "human" and e.is_meta:
            sections.append("_(元信息已折叠)_")
        elif e.kind == "human":
            sections.append("### 👤 用户\n\n" + e.text)
        elif e.kind == "assistant":
            sections.append("### 🤖 助手\n\n" + _render_assistant(
                e, truncate_at, no_raw, raw_files, subagent_links))
        elif e.kind == "tool_result":
            sections.append(_render_tool_result(e, truncate_at, no_raw, raw_files))

    return "\n\n".join(sections) + "\n", raw_files


def _render_assistant(e, truncate_at, no_raw, raw_files, subagent_links):
    parts = []
    for b in e.blocks:
        if b.kind == "thinking":
            parts.append(_blockquote("💭 **思考**\n" + b.text))
        elif b.kind == "text":
            parts.append(b.text)
        elif b.kind == "tool_use":
            body = config.dump_json(b.tool_input if b.tool_input is not None else {})
            body = _cut(body, b.tool_id + ".input", truncate_at, no_raw, raw_files)
            piece = "🔧 **%s** · `%s`\n\n%s" % (b.name, b.tool_id, _fence(body, "json"))
            if b.tool_id in subagent_links:
                link = subagent_links[b.tool_id]
                piece += "\n\n↳ 子代理转写:[%s](%s)" % (link, link)
            parts.append(piece)
    return "\n\n".join(parts)


def _render_tool_result(e, truncate_at, no_raw, raw_files):
    mark = " ❌" if e.is_error else ""
    text = e.blocks[0].text if e.blocks else ""
    body = _cut(text, e.tool_id or "result", truncate_at, no_raw, raw_files)
    return "### ↩️ 工具结果 · `%s`%s\n\n%s" % (e.tool_id, mark, _fence(body))


def _cut(text, key, truncate_at, no_raw, raw_files):
    """Truncate over-long text, registering the full body under ``raw/<key>.txt``."""
    if len(text) <= truncate_at:
        return text
    head = text[:truncate_at]
    if no_raw:
        note = "_[内容超长,已截断 %d 字符;raw/ 已关闭(--no-raw)]_" % len(text)
    else:
        raw_files["raw/%s.txt" % key] = text
        note = "_[内容超长,已截断 %d 字符 → 见 `raw/%s.txt`]_" % (len(text), key)
    return head + "\n" + note
