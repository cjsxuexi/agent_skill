# -*- coding: utf-8 -*-
"""index: cross-session INDEX.md / index.json, deterministic rollup, byte-exact idempotency."""
import json

from session_export import config, index


def _summary(sid, title, first_ts, h=1, a=1, tc=0, te=0, frictions=None):
    return {
        "session_id": sid, "title": title,
        "first_timestamp": first_ts, "last_timestamp": first_ts,
        "metrics": {"human_turns": h, "assistant_turns": a, "tool_calls": tc, "tool_errors": te},
        "frictions": frictions or [],
    }


def _seed(tmp_path):
    root = tmp_path / "export"
    config.write_json(root / "2026-06-19_乙_sidB1234" / "summary.json",
                      _summary("sidB1234-x", "会话乙", "2026-06-19T10:00:00Z", h=2, tc=3, te=1,
                               frictions=[{"type": "tool_error", "index": 1}]))
    config.write_json(root / "2026-06-18_甲_sidA1234" / "summary.json",
                      _summary("sidA1234-x", "会话甲", "2026-06-18T10:00:00Z", h=1, tc=1))
    return root


def test_index_builds_from_summaries(tmp_path):
    root = _seed(tmp_path)
    d, md = index.build_index(root, exported_at="2026-07-02T00:00:00Z")
    assert d["session_count"] == 2
    assert d["rollup"]["total_tool_calls"] == 4
    assert d["rollup"]["total_tool_errors"] == 1
    assert d["rollup"]["total_frictions"] == 1
    assert [s["session_id"] for s in d["sessions"]] == ["sidA1234-x", "sidB1234-x"]  # by first_ts
    assert "会话甲" in md and "会话乙" in md
    assert (root / "INDEX.md").is_file() and (root / "index.json").is_file()


def test_index_idempotent_byte_identical(tmp_path):
    root = _seed(tmp_path)
    index.build_index(root, exported_at="2026-07-02T00:00:00Z")
    md1 = (root / "INDEX.md").read_bytes()
    js1 = (root / "index.json").read_bytes()
    index.build_index(root, exported_at="2026-07-02T00:00:00Z")
    assert (root / "INDEX.md").read_bytes() == md1
    assert (root / "index.json").read_bytes() == js1


def test_index_empty_export_root(tmp_path):
    root = tmp_path / "export"
    root.mkdir()
    d, md = index.build_index(root, exported_at="2026-07-02T00:00:00Z")
    assert d["session_count"] == 0
    assert d["rollup"]["total_tool_calls"] == 0
    assert (root / "INDEX.md").is_file()


def test_index_table_escapes_pipe(tmp_path):
    root = tmp_path / "export"
    config.write_json(root / "d1" / "summary.json",
                      _summary("s1", "a|b table breaker", "2026-06-18T10:00:00Z"))
    _, md = index.build_index(root, exported_at="2026-07-02T00:00:00Z")
    assert "a\\|b" in md                         # pipe escaped, table not broken


def test_index_no_bom(tmp_path):
    root = _seed(tmp_path)
    index.build_index(root, exported_at="2026-07-02T00:00:00Z")
    assert not (root / "INDEX.md").read_bytes().startswith(b"\xef\xbb\xbf")
    assert not (root / "index.json").read_bytes().startswith(b"\xef\xbb\xbf")
    assert json.loads((root / "index.json").read_text(encoding="utf-8"))["session_count"] == 2
