# -*- coding: utf-8 -*-
"""catalog: top-level session discovery (subagents excluded), stable order, cache reuse/invalidation."""
import json
from pathlib import Path

import builders as B
from session_export import catalog


def _make_projects(tmp_path):
    root = tmp_path / "projects"
    # project A: one session + a subagent file that MUST be ignored
    a = root / "D--proj-a"
    B.write_jsonl(a / "sidA.jsonl", [
        B.ai_title("sidA", "会话甲"),
        B.human("sidA", "问甲", uuid="h1", ts="2026-06-18T10:00:00Z"),
        B.assistant("sidA", [B.tool_use("t1", "Read", {})], uuid="a1", ts="2026-06-18T10:00:01Z"),
    ])
    B.write_jsonl(a / "sidA" / "subagents" / "agent-aaa.jsonl", [
        B.assistant("sidA", [B.text("sub")], uuid="s1", is_sidechain=True)])
    # project B: one session, later timestamp
    b = root / "D--proj-b"
    B.write_jsonl(b / "sidB.jsonl", [
        B.ai_title("sidB", "会话乙"),
        B.human("sidB", "问乙", uuid="h1", ts="2026-06-19T10:00:00Z")])
    return root


def test_catalog_finds_top_level_only(tmp_path):
    root = _make_projects(tmp_path)
    metas = catalog.catalog(root, cache_path=tmp_path / "cache.json")
    ids = [m.session_id for m in metas]
    assert ids == ["sidA", "sidB"]                 # subagent file excluded


def test_catalog_meta_fields(tmp_path):
    root = _make_projects(tmp_path)
    metas = catalog.catalog(root, cache_path=tmp_path / "cache.json")
    a = [m for m in metas if m.session_id == "sidA"][0]
    assert a.title == "会话甲"
    assert a.human_turns == 1 and a.tool_calls == 1
    assert a.first_timestamp == "2026-06-18T10:00:00Z"


def test_catalog_sorted_by_first_ts(tmp_path):
    root = _make_projects(tmp_path)
    metas = catalog.catalog(root, cache_path=tmp_path / "cache.json")
    assert [m.session_id for m in metas] == ["sidA", "sidB"]


def test_catalog_cache_is_reused_when_unchanged(tmp_path):
    root = _make_projects(tmp_path)
    cache = tmp_path / "cache.json"
    catalog.catalog(root, cache_path=cache)
    # Tamper the cached title (file on disk untouched -> size+mtime still match).
    data = json.loads(cache.read_text(encoding="utf-8"))
    key = [k for k in data if k.endswith("sidA.jsonl")][0]
    data[key]["meta"]["title"] = "STALE-CACHE-HIT"
    cache.write_text(json.dumps(data), encoding="utf-8")
    metas = catalog.catalog(root, cache_path=cache)
    a = [m for m in metas if m.session_id == "sidA"][0]
    assert a.title == "STALE-CACHE-HIT"            # proves cache was reused, not re-parsed


def test_catalog_cache_invalidated_on_change(tmp_path):
    root = _make_projects(tmp_path)
    cache = tmp_path / "cache.json"
    catalog.catalog(root, cache_path=cache)
    data = json.loads(cache.read_text(encoding="utf-8"))
    key = [k for k in data if k.endswith("sidA.jsonl")][0]
    data[key]["meta"]["title"] = "STALE"
    cache.write_text(json.dumps(data), encoding="utf-8")
    # Change the underlying file (size differs -> cache must invalidate).
    B.write_jsonl(root / "D--proj-a" / "sidA.jsonl", [
        B.ai_title("sidA", "新的会话甲标题内容更长"),
        B.human("sidA", "新问", uuid="h1", ts="2026-06-18T10:00:00Z")])
    metas = catalog.catalog(root, cache_path=cache)
    a = [m for m in metas if m.session_id == "sidA"][0]
    assert a.title == "新的会话甲标题内容更长"     # recomputed, stale cache ignored
