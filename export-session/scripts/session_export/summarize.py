# -*- coding: utf-8 -*-
"""§10 summary.json: deterministic metrics, tool usage and friction extraction.

Frictions (D1's core input, design §10) are heuristic but fully reproducible:
same session -> same list, sorted by event index.
"""

# Correction cues (heuristic, EN + CN). Matched case-insensitively as substrings.
_CORRECTION_CUES = (
    "that's wrong", "that is wrong", "wrong", "not what", "no,", "no.",
    "actually", "instead", "revert", "undo", "don't", "do not",
    "不对", "错了", "不是这", "不是我", "别这", "重来", "重新", "撤销", "回退", "搞错",
)
_PERMISSION_CUES = (
    "permission", "not granted", "haven't granted", "hasn't granted",
    "requested permissions", "declined", "denied", "权限", "拒绝",
)
_DETAIL_MAXLEN = 200


def _detail(text):
    one = " ".join((text or "").split())
    return one[:_DETAIL_MAXLEN]


def summarize(session, exported_at=""):
    events = session.events

    tool_names = {}            # tool_use_id -> tool name
    tool_usage = {}
    thinking_blocks = tool_calls = 0
    human_turns = assistant_turns = tool_results = tool_errors = 0
    meta_lines = attachments = system_events = bookkeeping_lines = 0
    first_ts = last_ts = ""

    for e in events:
        if e.timestamp:
            first_ts = first_ts or e.timestamp
            last_ts = e.timestamp
        if e.kind == "human":
            if e.is_meta:
                meta_lines += 1
            else:
                human_turns += 1
        elif e.kind == "assistant":
            assistant_turns += 1
            for b in e.blocks:
                if b.kind == "thinking":
                    thinking_blocks += 1
                elif b.kind == "tool_use":
                    tool_calls += 1
                    tool_names[b.tool_id] = b.name
                    tool_usage[b.name] = tool_usage.get(b.name, 0) + 1
        elif e.kind == "tool_result":
            tool_results += 1
            if e.is_error:
                tool_errors += 1
        elif e.kind == "attachment":
            attachments += 1
        elif e.kind == "system":
            system_events += 1
        elif e.kind == "bookkeeping":
            bookkeeping_lines += 1

    frictions = _frictions(events, tool_names)

    metrics = {
        "human_turns": human_turns,
        "assistant_turns": assistant_turns,
        "tool_calls": tool_calls,
        "tool_results": tool_results,
        "tool_errors": tool_errors,
        "thinking_blocks": thinking_blocks,
        "attachments": attachments,
        "system_events": system_events,
        "meta_lines": meta_lines,
        "bookkeeping_lines": bookkeeping_lines,
        "total_events": len(events),
        "parse_errors": session.parse_errors,
    }
    return {
        "session_id": session.session_id,
        "title": session.title,
        "cwd": session.cwd,
        "git_branch": session.git_branch,
        "version": session.version,
        "first_timestamp": first_ts,
        "last_timestamp": last_ts,
        "exported_at": exported_at,
        "metrics": metrics,
        "tool_usage": dict(sorted(tool_usage.items())),
        "frictions": frictions,
    }


def _frictions(events, tool_names):
    frictions = []
    last_tool_name = None
    last_tool_errored = False
    saw_assistant = False

    for i, e in enumerate(events):
        if e.kind == "assistant":
            saw_assistant = True
            for b in e.blocks:
                if b.kind != "tool_use":
                    continue
                if last_tool_name == b.name and last_tool_errored:
                    frictions.append({"type": "retry", "index": i, "tool": b.name,
                                      "detail": "retried %s after a failed call" % b.name})
                last_tool_name = b.name
                last_tool_errored = False       # reset until we see its result
        elif e.kind == "tool_result":
            text_low = (e.blocks[0].text if e.blocks else "").lower()
            if any(cue in text_low for cue in _PERMISSION_CUES):
                frictions.append({"type": "permission_denied", "index": i,
                                  "tool": tool_names.get(e.tool_id, ""),
                                  "detail": _detail(e.blocks[0].text if e.blocks else "")})
                last_tool_errored = True
            elif e.is_error:
                frictions.append({"type": "tool_error", "index": i,
                                  "tool": tool_names.get(e.tool_id, ""),
                                  "detail": _detail(e.blocks[0].text if e.blocks else "")})
                last_tool_errored = True
        elif e.kind == "human" and not e.is_meta and saw_assistant:
            low = (e.text or "").lower()
            if any(cue in low for cue in _CORRECTION_CUES):
                frictions.append({"type": "user_correction", "index": i, "tool": "",
                                  "detail": _detail(e.text)})

    frictions.sort(key=lambda f: (f["index"], f["type"]))
    return frictions
