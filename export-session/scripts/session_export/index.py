# -*- coding: utf-8 -*-
"""index: recompute cross-session ``index.json`` + ``INDEX.md`` from every
``<export_root>/*/summary.json`` (design §10).

Full recompute each run — no incremental state — so it is idempotent: same inputs
+ same ``exported_at`` produce byte-identical files.
"""
import json
from pathlib import Path

from . import config

WARN = "> ⚠ 各会话产物可能含密钥 / 内部 URL,复用或外传前请自查。"


def _cell(text):
    return str(text).replace("|", "\\|").replace("\n", " ").strip()


def build_index(export_root, exported_at=""):
    root = Path(export_root)
    sessions = []
    for summ_path in sorted(root.glob("*/summary.json")):
        try:
            s = json.loads(summ_path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        m = s.get("metrics", {})
        sessions.append({
            "session_id": s.get("session_id", ""),
            "title": s.get("title", ""),
            "dir": summ_path.parent.name,
            "first_timestamp": s.get("first_timestamp", ""),
            "last_timestamp": s.get("last_timestamp", ""),
            "human_turns": m.get("human_turns", 0),
            "assistant_turns": m.get("assistant_turns", 0),
            "tool_calls": m.get("tool_calls", 0),
            "tool_errors": m.get("tool_errors", 0),
            "frictions": len(s.get("frictions", [])),
        })

    sessions.sort(key=lambda x: (x["first_timestamp"], x["session_id"]))

    rollup = {
        "total_human_turns": sum(x["human_turns"] for x in sessions),
        "total_assistant_turns": sum(x["assistant_turns"] for x in sessions),
        "total_tool_calls": sum(x["tool_calls"] for x in sessions),
        "total_tool_errors": sum(x["tool_errors"] for x in sessions),
        "total_frictions": sum(x["frictions"] for x in sessions),
    }
    index_json = {
        "generated_at": exported_at,
        "session_count": len(sessions),
        "rollup": rollup,
        "sessions": sessions,
    }

    md = _render_md(index_json)
    config.write_json(root / "index.json", index_json)
    config.write_text(root / "INDEX.md", md)
    return index_json, md


def _render_md(ix):
    r = ix["rollup"]
    lines = [
        "# 会话导出索引",
        "",
        WARN,
        "",
        "- generated_at: `%s`" % ix["generated_at"],
        "- 会话数: %d" % ix["session_count"],
        "- 汇总:用户轮次 %d / 助手轮次 %d / 工具调用 %d / 工具错误 %d / 摩擦点 %d" % (
            r["total_human_turns"], r["total_assistant_turns"], r["total_tool_calls"],
            r["total_tool_errors"], r["total_frictions"]),
        "",
        "| 会话 | 标题 | 起始 | 用户 | 助手 | 工具 | 错误 | 摩擦 | 目录 |",
        "| -- | -- | -- | -- | -- | -- | -- | -- | -- |",
    ]
    for s in ix["sessions"]:
        d = s["dir"]
        lines.append("| `%s` | %s | %s | %d | %d | %d | %d | %d | [%s](%s/) |" % (
            _cell(s["session_id"][:8]), _cell(s["title"]), _cell(s["first_timestamp"]),
            s["human_turns"], s["assistant_turns"], s["tool_calls"], s["tool_errors"],
            s["frictions"], _cell(d), d))
    return "\n".join(lines) + "\n"
