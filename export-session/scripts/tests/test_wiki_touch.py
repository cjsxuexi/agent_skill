# -*- coding: utf-8 -*-
"""wiki_touch: deterministic detection of a session's wiki touchpoints + fetching
the referenced wiki original text (design §3 wiki_touch, §4 step 4, D2 input)."""
import builders as B
from session_export import parse, wiki_touch


def _session(tmp_path, records):
    p = tmp_path / "s.jsonl"
    B.write_jsonl(p, records)
    return parse.parse_session(p)


def test_read_of_wiki_file_is_a_touch_and_fetches_original(tmp_path):
    wiki = tmp_path / "wiki"
    doc = wiki / "fms" / "index.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("# FMS 架构\n索引原文内容", encoding="utf-8")
    s = _session(tmp_path, [
        B.assistant("sid", [B.tool_use("t1", "Read", {"file_path": str(doc)})], uuid="a1"),
    ])
    touches = wiki_touch.detect_wiki_touches(s, wiki_root=str(wiki))
    assert len(touches) == 1
    t = touches[0]
    assert t.kind == "read_wiki_file"
    assert t.ref == str(doc)
    assert "索引原文内容" in t.quoted_original       # 取到被引 wiki 原文
    assert t.confidence == "high"


def test_read_of_nonwiki_file_is_not_a_touch(tmp_path):
    s = _session(tmp_path, [
        B.assistant("sid", [B.tool_use("t1", "Read", {"file_path": "D:\\proj\\main.py"})], uuid="a1"),
    ])
    assert wiki_touch.detect_wiki_touches(s, wiki_root="D:\\wiki") == []


def test_read_of_missing_wiki_file_is_low_confidence_no_original(tmp_path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    missing = wiki / "gone.md"
    s = _session(tmp_path, [
        B.assistant("sid", [B.tool_use("t1", "Read", {"file_path": str(missing)})], uuid="a1"),
    ])
    t = wiki_touch.detect_wiki_touches(s, wiki_root=str(wiki))[0]
    assert t.kind == "read_wiki_file"
    assert t.quoted_original is None
    assert t.confidence == "low"


def test_grep_and_glob_under_wiki_are_touches(tmp_path):
    s = _session(tmp_path, [
        B.assistant("sid", [
            B.tool_use("t1", "Grep", {"pattern": "架构", "path": "D:\\wiki"}),
            B.tool_use("t2", "Glob", {"pattern": "**/*.md", "path": "D:\\wiki\\fms"}),
        ], uuid="a1"),
    ])
    touches = wiki_touch.detect_wiki_touches(s, wiki_root="D:\\wiki")
    kinds = [t.kind for t in touches]
    assert kinds == ["grep_wiki", "glob_wiki"]
    assert "架构" in touches[0].ref
    assert all(t.confidence == "low" and t.quoted_original is None for t in touches)


def test_grep_outside_wiki_is_not_a_touch(tmp_path):
    s = _session(tmp_path, [
        B.assistant("sid", [B.tool_use("t1", "Grep", {"pattern": "x", "path": "D:\\code"})], uuid="a1"),
    ])
    assert wiki_touch.detect_wiki_touches(s, wiki_root="D:\\wiki") == []


def test_webfetch_of_wiki_url_is_a_touch(tmp_path):
    s = _session(tmp_path, [
        B.assistant("sid", [
            B.tool_use("t1", "WebFetch", {"url": "https://ones.example.com/wiki/page/123", "prompt": "读一下"}),
            B.tool_use("t2", "WebFetch", {"url": "https://multica.ai/docs", "prompt": "非 wiki"}),
        ], uuid="a1"),
    ])
    touches = wiki_touch.detect_wiki_touches(s, wiki_root="D:\\wiki")
    assert [t.kind for t in touches] == ["webfetch_wiki"]
    assert touches[0].ref == "https://ones.example.com/wiki/page/123"


def test_ones_wiki_mcp_call_is_a_touch(tmp_path):
    s = _session(tmp_path, [
        B.assistant("sid", [
            B.tool_use("t1", "mcp__ones_wiki__ones_wiki_get_page", {"page_id": "42"}),
        ], uuid="a1"),
    ])
    t = wiki_touch.detect_wiki_touches(s, wiki_root="D:\\wiki")[0]
    assert t.kind == "ones_wiki_mcp"
    assert t.tool == "mcp__ones_wiki__ones_wiki_get_page"
    assert "42" in t.ref


def test_document_systems_and_wiki_refine_skills_are_touches(tmp_path):
    s = _session(tmp_path, [
        B.assistant("sid", [B.tool_use("t1", "Skill", {"skill": "document-systems"})], uuid="a1"),
        B.assistant("sid", [B.tool_use("t2", "Skill", {"skill": "wiki-refine"})], uuid="a2"),
        B.assistant("sid", [B.tool_use("t3", "Skill", {"skill": "cmdcap"})], uuid="a3"),  # not wiki
    ])
    touches = wiki_touch.detect_wiki_touches(s, wiki_root="D:\\wiki")
    assert [t.kind for t in touches] == ["skill_document_systems", "skill_wiki_refine"]


def test_wiki_refine_slash_command_in_human_text_is_a_touch(tmp_path):
    s = _session(tmp_path, [
        B.human("sid", "/wiki-refine 帮我补充 FMS 文档", uuid="h1"),
    ])
    touches = wiki_touch.detect_wiki_touches(s, wiki_root="D:\\wiki")
    assert [t.kind for t in touches] == ["skill_wiki_refine"]


def test_touches_sorted_by_event_index_deterministic(tmp_path):
    s = _session(tmp_path, [
        B.assistant("sid", [B.tool_use("t1", "Skill", {"skill": "document-systems"})], uuid="a1"),
        B.human("sid", "普通消息", uuid="h1"),
        B.assistant("sid", [B.tool_use("t2", "mcp__ones_wiki__ones_wiki_search", {"q": "fms"})], uuid="a2"),
    ])
    touches = wiki_touch.detect_wiki_touches(s, wiki_root="D:\\wiki")
    assert [t.index for t in touches] == sorted(t.index for t in touches)
    assert [t.kind for t in touches] == ["skill_document_systems", "ones_wiki_mcp"]
