# -*- coding: utf-8 -*-
"""§11 config & detection: projects-root probing, config round-trip, slug/IO helpers."""
import io
import json
from pathlib import Path

from session_export import config


# ---- detect_projects_root precedence (design §11) ----
def test_override_always_wins(tmp_path):
    env = {"CLAUDE_CONFIG_DIR": str(tmp_path), "HOME": str(tmp_path), "USERPROFILE": str(tmp_path)}
    assert config.detect_projects_root(env, override=str(tmp_path / "custom")) == tmp_path / "custom"


def test_claude_config_dir_precedence(tmp_path):
    ccd = tmp_path / "cfg"
    (ccd / "projects").mkdir(parents=True)
    (tmp_path / "home" / ".claude" / "projects").mkdir(parents=True)
    env = {"CLAUDE_CONFIG_DIR": str(ccd), "HOME": str(tmp_path / "home")}
    assert config.detect_projects_root(env) == ccd / "projects"


def test_home_used_when_no_config_dir(tmp_path):
    home_proj = tmp_path / "home" / ".claude" / "projects"
    home_proj.mkdir(parents=True)
    env = {"HOME": str(tmp_path / "home")}
    assert config.detect_projects_root(env) == home_proj


def test_userprofile_fallback(tmp_path):
    up_proj = tmp_path / "up" / ".claude" / "projects"
    up_proj.mkdir(parents=True)
    env = {"USERPROFILE": str(tmp_path / "up")}
    assert config.detect_projects_root(env) == up_proj


def test_best_effort_when_none_exist(tmp_path):
    # Nothing on disk: still returns a Path (does not crash), preferring USERPROFILE.
    env = {"USERPROFILE": str(tmp_path / "up")}
    got = config.detect_projects_root(env)
    assert got == tmp_path / "up" / ".claude" / "projects"


# ---- Config round-trip via .config.json (UTF-8, no BOM) ----
def test_config_defaults_when_missing(tmp_path):
    cfg = config.load_config(str(tmp_path))
    assert cfg.export_root == str(tmp_path)
    assert cfg.wiki_root == "D:\\wiki"
    assert cfg.no_raw is False


def test_config_save_load_roundtrip(tmp_path):
    cfg = config.Config(export_root=str(tmp_path), wiki_root="D:\\other-wiki",
                        projects_root="P:\\proj", no_raw=True)
    config.save_config(cfg)
    again = config.load_config(str(tmp_path))
    assert again == cfg


def test_config_json_is_utf8_no_bom(tmp_path):
    cfg = config.Config(export_root=str(tmp_path), wiki_root="D:\\维基")
    config.save_config(cfg)
    raw = (tmp_path / ".config.json").read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")           # no BOM
    assert "维基" in raw.decode("utf-8")                  # CJK preserved


# ---- slugify: keep CJK, strip illegal filename chars (design §14) ----
def test_slug_keeps_cjk_and_dot():
    assert config.slugify("检查SKILL.md中S-path说明的语义") == "检查SKILL.md中S-path说明的语义"


def test_slug_strips_illegal_chars():
    assert config.slugify('a/b\\c:d*e?f"g<h>i|j') == "abcdefghij"


def test_slug_collapses_whitespace():
    assert config.slugify("  hello   world \t nihao  ") == "hello_world_nihao"


def test_slug_empty_becomes_session():
    assert config.slugify("") == "session"
    assert config.slugify('///:::') == "session"


def test_slug_length_capped():
    assert config.slugify("超" * 100) == "超" * 40


# ---- deterministic JSON / no-BOM text helpers ----
def test_write_json_deterministic_no_bom(tmp_path):
    p = tmp_path / "x.json"
    obj = {"b": 1, "a": "中文", "list": [3, 2, 1]}
    config.write_json(p, obj)
    raw = p.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    # insertion order preserved (not sorted), CJK inline, trailing newline
    assert raw.decode("utf-8") == '{\n  "b": 1,\n  "a": "中文",\n  "list": [\n    3,\n    2,\n    1\n  ]\n}\n'
    assert json.loads(p.read_text(encoding="utf-8")) == obj


def test_write_text_lf_newlines_no_bom(tmp_path):
    p = tmp_path / "x.md"
    config.write_text(p, "line1\nline2\n中文\n")
    raw = p.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" not in raw                             # LF only, deterministic across OS
    assert raw.decode("utf-8") == "line1\nline2\n中文\n"
