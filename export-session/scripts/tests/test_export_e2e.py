# -*- coding: utf-8 -*-
"""End-to-end orchestration: export dir naming, raw/, subagents, INDEX recompute,
and the design §14 hard requirement: same input + injected exported_at -> byte-identical."""
import builders as B
from session_export import export

TS = "2026-07-02T00:00:00Z"
SID = "abcd1234-0000-0000-0000-000000000000"


def _main_session(root, sid=SID, title="导出引擎测试", with_subagent=False, with_long=False):
    """Write a main session (+ optional subagent) under a projects-style layout; return jsonl path."""
    proj = root / "D--proj"
    blocks = [B.thinking("推理"), B.text("答复")]
    if with_subagent:
        blocks.append(B.tool_use("tu1", "Agent", {"description": "子任务"}))
    recs = [
        B.ai_title(sid, title),
        B.mode(sid),
        B.human(sid, "请开始", uuid="h1", ts="2026-06-18T15:00:00Z"),
        B.assistant(sid, blocks, uuid="a1", parent="h1", ts="2026-06-18T15:00:01Z"),
    ]
    if with_long:
        recs.append(B.assistant(sid, [B.tool_use("tu2", "Bash", {})], uuid="a2", ts="2026-06-18T15:00:02Z"))
        recs.append(B.tool_result(sid, "tu2", "L" * 5000, uuid="r2", ts="2026-06-18T15:00:03Z"))
    main = proj / (sid + ".jsonl")
    B.write_jsonl(main, recs)
    if with_subagent:
        sub = proj / sid / "subagents" / "agent-aaa111.jsonl"
        B.write_jsonl(sub, [B.assistant(sid, [B.text("子代理结果")], uuid="s1", is_sidechain=True)])
        (proj / sid / "subagents" / "agent-aaa111.meta.json").write_text(
            '{"agentType":"general-purpose","description":"子任务","toolUseId":"tu1"}', encoding="utf-8")
    return main


def test_export_produces_expected_files_and_dirname(tmp_path):
    main = _main_session(tmp_path / "projects")
    res = export.export_session(main, tmp_path / "export", exported_at=TS)
    d = res["export_dir"]
    assert d.name == "2026-06-18_导出引擎测试_abcd1234"     # date_slug_id8, CJK preserved
    assert (d / "transcript.md").is_file()
    assert (d / "summary.json").is_file()
    txt = (d / "transcript.md").read_text(encoding="utf-8")
    assert "答复" in txt and "推理" in txt


def test_export_long_result_writes_raw(tmp_path):
    main = _main_session(tmp_path / "projects", with_long=True)
    res = export.export_session(main, tmp_path / "export", exported_at=TS, truncate_at=100)
    raw = res["export_dir"] / "raw" / "tu2.txt"
    assert raw.is_file()
    assert raw.read_text(encoding="utf-8") == "L" * 5000


def test_export_no_raw_skips_raw_dir(tmp_path):
    main = _main_session(tmp_path / "projects", with_long=True)
    res = export.export_session(main, tmp_path / "export", exported_at=TS, truncate_at=100, no_raw=True)
    assert not (res["export_dir"] / "raw").exists()


def test_export_subagent_linked_and_written(tmp_path):
    main = _main_session(tmp_path / "projects", with_subagent=True)
    res = export.export_session(main, tmp_path / "export", exported_at=TS)
    d = res["export_dir"]
    sub_md = d / "subagents" / "agent-aaa111.md"
    assert sub_md.is_file()
    assert "子代理结果" in sub_md.read_text(encoding="utf-8")
    # main transcript links to the subagent transcript at its Agent tool call
    assert "subagents/agent-aaa111.md" in (d / "transcript.md").read_text(encoding="utf-8")


def test_export_empty_session(tmp_path):
    proj = tmp_path / "projects" / "D--proj"
    main = proj / ("empty000-0000-0000-0000-000000000000.jsonl")
    B.write_jsonl(main, [])
    res = export.export_session(main, tmp_path / "export", exported_at=TS)
    assert (res["export_dir"] / "transcript.md").is_file()
    assert (res["export_dir"] / "summary.json").is_file()


def test_export_is_byte_identical_across_runs(tmp_path):
    """§14 determinism: same input + injected exported_at => byte-for-byte identical output."""
    main = _main_session(tmp_path / "projects", with_subagent=True, with_long=True)
    r1 = export.export_session(main, tmp_path / "e1", exported_at=TS, truncate_at=100)
    r2 = export.export_session(main, tmp_path / "e2", exported_at=TS, truncate_at=100)
    for rel in ("transcript.md", "summary.json", "subagents/agent-aaa111.md", "raw/tu2.txt"):
        b1 = (r1["export_dir"] / rel).read_bytes()
        b2 = (r2["export_dir"] / rel).read_bytes()
        assert b1 == b2, "non-deterministic output: " + rel
        assert not b1.startswith(b"\xef\xbb\xbf")             # UTF-8, no BOM


def test_cli_export_then_index(tmp_path):
    main = _main_session(tmp_path / "projects")
    eroot = tmp_path / "export"
    rc = export.main(["export", "--jsonl", str(main), "--export-root", str(eroot), "--exported-at", TS])
    assert rc == 0
    assert (eroot / "INDEX.md").is_file() and (eroot / "index.json").is_file()
    assert (eroot / "2026-06-18_导出引擎测试_abcd1234" / "transcript.md").is_file()


def test_cli_export_by_session_id(tmp_path):
    proot = tmp_path / "projects"
    _main_session(proot)
    eroot = tmp_path / "export"
    rc = export.main(["export", "--session-id", SID, "--projects-root", str(proot),
                      "--export-root", str(eroot), "--exported-at", TS])
    assert rc == 0
    assert (eroot / "2026-06-18_导出引擎测试_abcd1234" / "summary.json").is_file()


def test_cli_index_only(tmp_path):
    main = _main_session(tmp_path / "projects")
    eroot = tmp_path / "export"
    export.export_session(main, eroot, exported_at=TS)
    rc = export.main(["index", "--export-root", str(eroot), "--exported-at", TS])
    assert rc == 0
    assert (eroot / "INDEX.md").is_file()
