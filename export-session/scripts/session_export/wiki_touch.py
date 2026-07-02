# -*- coding: utf-8 -*-
"""wiki_touch — deterministically mark a session's **wiki touchpoints** and fetch
the referenced wiki original text (design §3 / §4 step 4; D2's input).

A *touchpoint* is any point where the session used the wiki:
- ``Read`` of a file under ``wiki_root``  → the original text is fetched (D2 can
  compare "how the agent used it" against the real page).
- ``Grep`` / ``Glob`` whose ``path`` is under ``wiki_root``.
- ``WebFetch`` of a wiki URL (url contains ``wiki``).
- any ``mcp__ones_wiki__*`` tool call.
- ``document-systems`` / ``wiki-refine`` skill use (``Skill`` tool, or a
  ``/document-systems`` · ``/wiki-refine`` slash command in a human turn).

Pure & deterministic: no LLM, no network — the only IO is reading a referenced
wiki file that already exists on disk. Touches come back sorted by event index.
"""
import os
from dataclasses import dataclass

from . import config

DEFAULT_QUOTE_MAXLEN = 2000
_ONES_WIKI_PREFIX = "mcp__ones_wiki__"
_WIKI_SKILLS = {"document-systems": "skill_document_systems", "wiki-refine": "skill_wiki_refine"}


@dataclass
class WikiTouch:
    kind: str                    # read_wiki_file | grep_wiki | glob_wiki | webfetch_wiki | ones_wiki_mcp | skill_document_systems | skill_wiki_refine
    tool: str                    # tool name (Read / Grep / WebFetch / mcp__… / Skill / slash-command)
    index: int                   # event index in session.events
    ref: str                     # referenced path / url / page / query
    tool_id: str = ""
    quoted_original: str = None   # fetched wiki original text (only when reachable)
    confidence: str = "low"       # "high" only when the exact original was fetched


def _norm(p):
    return os.path.normcase(os.path.normpath(str(p)))


def _under(path, root):
    """True if ``path`` is ``root`` or lives beneath it (separator/-case-insensitive)."""
    if not path:
        return False
    p, r = _norm(path), _norm(root)
    return p == r or p.startswith(r + os.sep)


def _fetch_original(path, max_quote):
    try:
        text = config.read_text(path)
    except (OSError, ValueError):
        return None
    return text[:max_quote]


def _touch_from_tool_use(b, idx, wiki_root, fetch, max_quote):
    """Map one ``tool_use`` block to a WikiTouch, or ``None`` if it isn't a touch."""
    name, inp = b.name, (b.tool_input or {})

    if name == "Read":
        fp = inp.get("file_path", "")
        if _under(fp, wiki_root):
            original = _fetch_original(fp, max_quote) if fetch else None
            return WikiTouch(kind="read_wiki_file", tool=name, index=idx, ref=fp,
                             tool_id=b.tool_id, quoted_original=original,
                             confidence="high" if original is not None else "low")
        return None

    if name in ("Grep", "Glob"):
        if _under(inp.get("path", ""), wiki_root):
            kind = "grep_wiki" if name == "Grep" else "glob_wiki"
            ref = inp.get("pattern", "")
            return WikiTouch(kind=kind, tool=name, index=idx, ref=ref, tool_id=b.tool_id)
        return None

    if name == "WebFetch":
        url = inp.get("url", "")
        if "wiki" in url.lower():
            return WikiTouch(kind="webfetch_wiki", tool=name, index=idx, ref=url, tool_id=b.tool_id)
        return None

    if name.startswith(_ONES_WIKI_PREFIX):
        ref = "; ".join("%s=%s" % (k, v) for k, v in sorted(inp.items())) or name
        return WikiTouch(kind="ones_wiki_mcp", tool=name, index=idx, ref=ref, tool_id=b.tool_id)

    if name == "Skill":
        kind = _WIKI_SKILLS.get(str(inp.get("skill", "")))
        if kind:
            return WikiTouch(kind=kind, tool=name, index=idx, ref=inp.get("skill", ""), tool_id=b.tool_id)
        return None

    return None


def _touch_from_human(e, idx):
    """A ``/document-systems`` or ``/wiki-refine`` slash command counts as wiki use."""
    first = (e.text or "").strip().splitlines()[0].strip() if (e.text or "").strip() else ""
    for slug, kind in _WIKI_SKILLS.items():
        if first == "/" + slug or first.startswith("/" + slug + " "):
            return WikiTouch(kind=kind, tool="slash-command", index=idx, ref="/" + slug)
    return None


def detect_wiki_touches(session, wiki_root=config.DEFAULT_WIKI_ROOT, fetch=True,
                        max_quote=DEFAULT_QUOTE_MAXLEN):
    """Return every wiki touchpoint in ``session``, sorted by event index."""
    touches = []
    for idx, e in enumerate(session.events):
        if e.kind == "assistant":
            for b in e.blocks:
                if b.kind == "tool_use":
                    t = _touch_from_tool_use(b, idx, wiki_root, fetch, max_quote)
                    if t is not None:
                        touches.append(t)
        elif e.kind == "human" and not e.is_meta:
            t = _touch_from_human(e, idx)
            if t is not None:
                touches.append(t)
    touches.sort(key=lambda t: t.index)
    return touches
