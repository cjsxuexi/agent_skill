# -*- coding: utf-8 -*-
"""Deterministic JSONL parser: one Claude Code session file -> normalized ``Session``.

Reads UTF-8, tolerates a truncated trailing line (design §13.3), and classifies
every line into an ``Event`` (bookkeeping rows are kept but flagged so ``render``
can drop them from the flow, design §10).
"""
import io
import json
from dataclasses import dataclass, field
from pathlib import Path

BOOKKEEPING_TYPES = {"mode", "permission-mode", "last-prompt", "file-history-snapshot", "ai-title"}
TITLE_MAXLEN = 80


@dataclass
class Block:
    kind: str                  # thinking | text | tool_use | tool_result
    text: str = ""
    name: str = ""             # tool name (tool_use)
    tool_id: str = ""          # tool_use id / tool_use_id
    tool_input: dict = None
    is_error: bool = False


@dataclass
class Event:
    kind: str                  # human | assistant | tool_result | attachment | system | bookkeeping
    subtype: str = ""          # bookkeeping type / system subtype / attachment type
    text: str = ""
    blocks: list = field(default_factory=list)
    uuid: str = ""
    parent_uuid: str = ""
    timestamp: str = ""
    model: str = ""
    is_meta: bool = False
    is_sidechain: bool = False
    tool_id: str = ""          # tool_result -> its tool_use_id
    is_error: bool = False


@dataclass
class Session:
    session_id: str
    title: str
    ai_title: str
    cwd: str
    git_branch: str
    version: str
    events: list
    parse_errors: int
    source_path: str


def _content_text(content):
    """Flatten a tool_result / message ``content`` (str or block list) to text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for b in content:
            if isinstance(b, dict):
                if b.get("type") == "text":
                    parts.append(b.get("text", ""))
                elif "text" in b:
                    parts.append(b.get("text", ""))
        return "\n".join(parts)
    return "" if content is None else str(content)


def _parse_assistant_blocks(content):
    blocks = []
    if isinstance(content, str):
        return [Block(kind="text", text=content)]
    for b in content or []:
        if not isinstance(b, dict):
            continue
        bt = b.get("type")
        if bt == "thinking":
            blocks.append(Block(kind="thinking", text=b.get("thinking", "")))
        elif bt == "text":
            blocks.append(Block(kind="text", text=b.get("text", "")))
        elif bt == "tool_use":
            blocks.append(Block(kind="tool_use", name=b.get("name", ""),
                                tool_id=b.get("id", ""), tool_input=b.get("input", {})))
    return blocks


def classify(obj):
    """Turn one raw jsonl object into an ``Event`` (never raises on shape)."""
    t = obj.get("type")
    base = dict(uuid=obj.get("uuid", ""), parent_uuid=obj.get("parentUuid") or "",
                timestamp=obj.get("timestamp", ""), is_sidechain=bool(obj.get("isSidechain")))

    if t in BOOKKEEPING_TYPES:
        text = obj.get("aiTitle", "") if t == "ai-title" else ""
        return Event(kind="bookkeeping", subtype=t, text=text, **base)

    if t == "attachment":
        att = obj.get("attachment") or {}
        return Event(kind="attachment", subtype=att.get("type", ""),
                     text=att.get("hookName", "") or att.get("type", ""), **base)

    if t == "system":
        return Event(kind="system", subtype=obj.get("subtype", ""), **base)

    if t == "assistant":
        msg = obj.get("message") or {}
        return Event(kind="assistant", blocks=_parse_assistant_blocks(msg.get("content")),
                     model=msg.get("model", ""), **base)

    if t == "user":
        msg = obj.get("message") or {}
        content = msg.get("content")
        is_meta = bool(obj.get("isMeta"))
        if isinstance(content, list) and any(
                isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
            for b in content:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    is_err = bool(b.get("is_error"))
                    blk = Block(kind="tool_result", text=_content_text(b.get("content")),
                                tool_id=b.get("tool_use_id", ""), is_error=is_err)
                    return Event(kind="tool_result", blocks=[blk], tool_id=blk.tool_id,
                                 is_error=is_err, is_meta=is_meta, **base)
        return Event(kind="human", text=_content_text(content), is_meta=is_meta, **base)

    # unknown/future line type: keep as bookkeeping so nothing is lost or crashes
    return Event(kind="bookkeeping", subtype=t or "unknown", **base)


def _derive_title(session_id, events, ai_title):
    if ai_title:
        return ai_title
    for e in events:
        if e.kind == "human" and not e.is_meta and e.text.strip():
            first_line = e.text.strip().splitlines()[0].strip()
            if first_line:
                return first_line[:TITLE_MAXLEN]
    return session_id


def parse_session(path):
    """Parse a session ``.jsonl`` into a ``Session`` (fault-tolerant, deterministic)."""
    path = Path(path)
    session_id = path.stem
    events, parse_errors = [], 0
    ai_title = ""
    cwd = git_branch = version = ""

    with io.open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except (ValueError, json.JSONDecodeError):
                parse_errors += 1
                continue
            if not isinstance(obj, dict):
                parse_errors += 1
                continue
            ev = classify(obj)
            events.append(ev)
            if ev.subtype == "ai-title" and ev.text:
                ai_title = ev.text            # last ai-title wins
            cwd = obj.get("cwd", cwd) or cwd
            git_branch = obj.get("gitBranch", git_branch) or git_branch
            version = obj.get("version", version) or version

    title = _derive_title(session_id, events, ai_title)
    return Session(session_id=session_id, title=title, ai_title=ai_title, cwd=cwd,
                   git_branch=git_branch, version=version, events=events,
                   parse_errors=parse_errors, source_path=str(path))
