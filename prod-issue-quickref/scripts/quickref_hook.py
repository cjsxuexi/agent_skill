#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""prod-issue-quickref session hooks (布防式 auto-record).

FAIL-OPEN by construction: on ANY error, or any unexpected input, do nothing and
exit 0 so normal Claude Code operation is never disrupted.

Modes:
  --arm   (wired on PostToolUse:Read): if the tool just read a `生产问题速查.md`,
          arm THIS session (touch a per-session marker). Never blocks.
  --stop  (wired on Stop): if this session is armed and not yet handled, emit
          {"decision":"block","reason":...} ONCE to nudge the model into the
          record/ask flow, then mark handled. Otherwise allow the stop.

Loop safety (two independent guards): honour `stop_hook_active`, AND a per-session
`.done` marker; if the `.done` marker can't be written, allow the stop rather than
risk an infinite block.

Markers: <tempdir>/prod-issue-quickref/<session_id>.{armed,done}
"""
import sys
import os
import json
import tempfile

STATE_DIR = os.path.join(tempfile.gettempdir(), "prod-issue-quickref")

REASON = (
    "本 session 疑似问题定位（其间读过某仓的 生产问题速查.md）。请按 prod-issue-quickref 技能的"
    "「记录 / 询问门禁」收尾：\n"
    "1) 若本次已明确定位到一个值得记录的生产问题根因（有现象 + 根因 + 可链接的 wiki 文档），"
    "就把它记入对应仓的 生产问题速查.md（现象根 → 判别分支 → 根因叶子 + wiki 链接），"
    "并跑 scripts/validate_quickref.py 校验；\n"
    "2) 若不确定是否该记（定位不全 / 不确定是不是生产问题），先用 AskUserQuestion 问用户要不要记；\n"
    "3) 若本次并非问题定位、或没定位到明确根因，直接正常结束——不要记也不要问。\n"
    "注意：若你是非交互的自动化 agent（如后台 / 任务运行），不要交互提问——能确信就记，否则直接结束。"
)


def _load_stdin():
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw and raw.strip() else {}
    except Exception:
        return {}


def _session_id(data):
    sid = data.get("session_id") or data.get("sessionId") or ""
    return "".join(c for c in str(sid) if c.isalnum() or c in "-_")


def _marker(sid, suffix):
    return os.path.join(STATE_DIR, sid + suffix)


def do_arm(data):
    try:
        tool = data.get("tool_name") or data.get("toolName") or ""
        ti = data.get("tool_input") or data.get("toolInput") or {}
        path = ""
        if isinstance(ti, dict):
            path = ti.get("file_path") or ti.get("filePath") or ti.get("path") or ""
        if tool == "Read" and str(path).replace("\\", "/").endswith("生产问题速查.md"):
            sid = _session_id(data)
            if sid:
                os.makedirs(STATE_DIR, exist_ok=True)
                open(_marker(sid, ".armed"), "w").close()
    except Exception:
        pass
    return 0  # PostToolUse must never block


def do_stop(data):
    try:
        if data.get("stop_hook_active") is True:
            return 0  # guard 1: we already continued once this chain -> allow stop
        sid = _session_id(data)
        if not sid:
            return 0
        if not os.path.exists(_marker(sid, ".armed")):
            return 0  # not a diagnosis-touching session
        if os.path.exists(_marker(sid, ".done")):
            return 0  # guard 2: already handled this session
        try:
            os.makedirs(STATE_DIR, exist_ok=True)
            open(_marker(sid, ".done"), "w").close()
        except Exception:
            return 0  # if we can't mark done, DON'T block (avoid any loop risk)
        sys.stdout.write(json.dumps({"decision": "block", "reason": REASON},
                                    ensure_ascii=False))
    except Exception:
        pass
    return 0


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    data = _load_stdin()
    if mode == "--arm":
        return do_arm(data)
    if mode == "--stop":
        return do_stop(data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
