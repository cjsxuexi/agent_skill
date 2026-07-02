# -*- coding: utf-8 -*-
"""catalog: discover top-level Claude Code sessions under a projects root.

Only ``<projects_root>/<projdir>/<session>.jsonl`` files are catalogued — sub-agent
and workflow journals live one directory deeper and are excluded (design §12/§13).
A ``.catalog-cache.json`` keyed by (size, mtime) avoids re-parsing unchanged files;
any size/mtime change invalidates the entry.
"""
import json
from dataclasses import dataclass, asdict
from pathlib import Path

from . import parse, summarize


@dataclass
class SessionMeta:
    session_id: str
    path: str
    title: str
    cwd: str
    git_branch: str
    first_timestamp: str
    last_timestamp: str
    human_turns: int
    assistant_turns: int
    tool_calls: int
    tool_errors: int
    total_events: int
    size_bytes: int


def _meta_from_session(path, size):
    s = parse.parse_session(path)
    d = summarize.summarize(s)
    m = d["metrics"]
    return SessionMeta(
        session_id=s.session_id, path=str(path), title=s.title, cwd=s.cwd,
        git_branch=s.git_branch, first_timestamp=d["first_timestamp"],
        last_timestamp=d["last_timestamp"], human_turns=m["human_turns"],
        assistant_turns=m["assistant_turns"], tool_calls=m["tool_calls"],
        tool_errors=m["tool_errors"], total_events=m["total_events"], size_bytes=size)


def _load_cache(cache_path):
    if cache_path and Path(cache_path).is_file():
        try:
            return json.loads(Path(cache_path).read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return {}
    return {}


def catalog(projects_root, cache_path=None):
    """Return ``SessionMeta`` for every top-level session, sorted by (first_ts, id)."""
    root = Path(projects_root)
    cache = _load_cache(cache_path)
    new_cache = {}
    metas = []

    for jsonl in sorted(root.glob("*/*.jsonl")):
        st = jsonl.stat()
        key = str(jsonl.resolve())
        entry = cache.get(key)
        if entry and entry.get("size") == st.st_size and entry.get("mtime") == st.st_mtime:
            meta = SessionMeta(**entry["meta"])
        else:
            meta = _meta_from_session(jsonl, st.st_size)
        new_cache[key] = {"size": st.st_size, "mtime": st.st_mtime, "meta": asdict(meta)}
        metas.append(meta)

    if cache_path is not None:
        Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
        Path(cache_path).write_text(
            json.dumps(new_cache, ensure_ascii=False, indent=2), encoding="utf-8")

    metas.sort(key=lambda m: (m.first_timestamp, m.session_id))
    return metas
