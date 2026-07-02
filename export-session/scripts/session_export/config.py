# -*- coding: utf-8 -*-
"""§11 configuration & detection + shared encoding-safe IO helpers.

All text/JSON writers emit UTF-8 **without BOM** and LF newlines so exports are
byte-for-byte reproducible across machines (design §14, windows-cn-shell-safety).
"""
import io
import json
import re
from dataclasses import dataclass, asdict, field
from pathlib import Path

DEFAULT_EXPORT_ROOT = "D:\\claude-sessions"
DEFAULT_WIKI_ROOT = "D:\\wiki"
CONFIG_FILENAME = ".config.json"

_ILLEGAL = set('\\/:*?"<>|')


def detect_projects_root(env, override=None):
    """Resolve the Claude Code ``projects`` root (design §11).

    Precedence: explicit ``override`` → ``$CLAUDE_CONFIG_DIR/projects`` →
    ``$HOME/.claude/projects`` → ``%USERPROFILE%\\.claude\\projects``. Among the
    env candidates the first that already exists on disk wins; if none exist the
    last (USERPROFILE) candidate is returned best-effort so callers get a Path,
    not ``None``.
    """
    if override:
        return Path(override)

    candidates = []
    ccd = env.get("CLAUDE_CONFIG_DIR")
    if ccd:
        candidates.append(Path(ccd) / "projects")
    home = env.get("HOME")
    if home:
        candidates.append(Path(home) / ".claude" / "projects")
    up = env.get("USERPROFILE")
    if up:
        candidates.append(Path(up) / ".claude" / "projects")

    for c in candidates:
        if c.is_dir():
            return c
    return candidates[-1] if candidates else Path(".claude") / "projects"


@dataclass
class Config:
    export_root: str = DEFAULT_EXPORT_ROOT
    projects_root: str = ""
    wiki_root: str = DEFAULT_WIKI_ROOT
    no_raw: bool = False


def load_config(export_root):
    """Load ``<export_root>/.config.json`` merged over defaults (missing → defaults)."""
    cfg = Config(export_root=str(export_root))
    p = Path(export_root) / CONFIG_FILENAME
    if p.is_file():
        data = json.loads(p.read_text(encoding="utf-8"))
        for k, v in data.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)
    cfg.export_root = str(export_root)
    return cfg


def save_config(cfg):
    write_json(Path(cfg.export_root) / CONFIG_FILENAME, asdict(cfg))


def slugify(title, maxlen=40):
    """Filesystem-safe slug that keeps CJK; strips ``\\ / : * ? " < > |`` and
    control chars; collapses whitespace runs to ``_``; caps to ``maxlen`` chars."""
    if title is None:
        return "session"
    out = []
    for ch in str(title):
        if ch in _ILLEGAL or ord(ch) < 0x20:
            continue
        out.append(ch)
    s = "".join(out)
    s = re.sub(r"\s+", "_", s.strip())
    s = s.strip("_. ")
    s = s[:maxlen].strip("_. ")
    return s or "session"


# ---- deterministic, no-BOM writers ----
def dump_json(obj):
    """Canonical JSON text: insertion order preserved, CJK inline, 2-space indent."""
    return json.dumps(obj, ensure_ascii=False, indent=2)


def write_json(path, obj):
    write_text(path, dump_json(obj) + "\n")


def write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return path


def read_text(path):
    return Path(path).read_text(encoding="utf-8")
