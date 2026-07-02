# -*- coding: utf-8 -*-
"""Synthetic Claude Code session-JSONL builders for tests.

Every builder returns a plain ``dict`` shaped exactly like a real
``~/.claude/projects/<enc>/<uuid>.jsonl`` line (verified against live sessions
on 2026-07-02). ``write_jsonl`` serialises records to UTF-8 (no BOM), and also
accepts raw ``str`` records so tests can inject malformed/truncated tail lines.
"""
import io
import json
from pathlib import Path

DEF_TS = "2026-06-18T15:04:00.000Z"


def write_jsonl(path, records):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        for r in records:
            if isinstance(r, str):
                f.write(r + "\n")            # raw line (e.g. a truncated tail)
            else:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return path


# ---- bookkeeping lines (must NOT appear in the transcript flow, design §10) ----
def ai_title(session_id, title):
    return {"type": "ai-title", "aiTitle": title, "sessionId": session_id}


def mode(session_id, mode="normal"):
    return {"type": "mode", "mode": mode, "sessionId": session_id}


def permission_mode(session_id, pm="default"):
    return {"type": "permission-mode", "permissionMode": pm, "sessionId": session_id}


def last_prompt(session_id, leaf="leaf-uuid"):
    return {"type": "last-prompt", "leafUuid": leaf, "sessionId": session_id}


def file_snapshot(message_id="m1"):
    return {
        "type": "file-history-snapshot",
        "messageId": message_id,
        "snapshot": {"messageId": message_id, "trackedFileBackups": {}, "timestamp": DEF_TS},
        "isSnapshotUpdate": False,
    }


# ---- real conversation lines ----
def human(session_id, text, uuid="u-h", parent=None, ts=DEF_TS, is_meta=False,
          cwd="D:\\proj", git="master", version="2.1.181"):
    return {
        "parentUuid": parent, "isSidechain": False, "type": "user",
        "message": {"role": "user", "content": text},
        "uuid": uuid, "timestamp": ts, "origin": {"kind": "human"},
        "isMeta": is_meta, "userType": "external", "entrypoint": "cli",
        "cwd": cwd, "sessionId": session_id, "version": version, "gitBranch": git,
    }


def assistant(session_id, blocks, uuid="u-a", parent=None, ts=DEF_TS,
              model="claude-opus-4-8", is_sidechain=False,
              cwd="D:\\proj", git="master", version="2.1.181"):
    return {
        "parentUuid": parent, "isSidechain": is_sidechain, "type": "assistant",
        "message": {"model": model, "id": "msg_x", "type": "message",
                    "role": "assistant", "content": blocks},
        "uuid": uuid, "timestamp": ts, "userType": "external", "entrypoint": "cli",
        "cwd": cwd, "sessionId": session_id, "version": version, "gitBranch": git,
    }


def thinking(text):
    return {"type": "thinking", "thinking": text, "signature": "sig-redacted"}


def text(t):
    return {"type": "text", "text": t}


def tool_use(tool_id, name, tool_input):
    return {"type": "tool_use", "id": tool_id, "name": name, "input": tool_input}


def tool_result(session_id, tool_use_id, content, uuid="u-tr", parent=None, ts=DEF_TS,
                is_error=False, tool_use_result=None, cwd="D:\\proj"):
    block = {"type": "tool_result", "tool_use_id": tool_use_id, "content": content}
    if is_error:
        block["is_error"] = True
    obj = {
        "parentUuid": parent, "isSidechain": False, "type": "user",
        "message": {"role": "user", "content": [block]},
        "uuid": uuid, "timestamp": ts, "userType": "external", "entrypoint": "cli",
        "cwd": cwd, "sessionId": session_id, "version": "2.1.181", "gitBranch": "master",
    }
    if tool_use_result is not None:
        obj["toolUseResult"] = tool_use_result
    return obj


def attachment(session_id, att, uuid="u-att", ts=DEF_TS, cwd="D:\\proj"):
    return {
        "parentUuid": None, "isSidechain": False, "type": "attachment",
        "attachment": att, "uuid": uuid, "timestamp": ts, "userType": "external",
        "entrypoint": "cli", "cwd": cwd, "sessionId": session_id,
        "version": "2.1.181", "gitBranch": "master",
    }


def system(session_id, subtype="turn_duration", uuid="u-sys", parent=None,
           ts=DEF_TS, duration_ms=1000, message_count=1):
    return {
        "parentUuid": parent, "isSidechain": False, "type": "system", "subtype": subtype,
        "durationMs": duration_ms, "messageCount": message_count, "timestamp": ts,
        "uuid": uuid, "isMeta": False, "userType": "external", "entrypoint": "cli",
        "cwd": "D:\\proj", "sessionId": session_id, "version": "2.1.181", "gitBranch": "master",
    }
