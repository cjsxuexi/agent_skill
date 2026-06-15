"""DocKind classification — the engine's first pass (plan §3, §6.1).

Order of decision for a path relative to ``doc_root``:
  1. directory namespace: a top-level ``_*`` segment is non-business — ``_common`` is
     COMMON, any other ``_*`` (e.g. ``_meta``) or a ``.``-prefixed dir is IGNORED;
  2. ignore globs (loaded from common-conventions.md) -> IGNORED;
  3. ``architecture.md`` at the doc-root top -> ROOT or SINGLE (by content);
  4. ``<subsystem>/architecture.md`` -> SUBSYSTEM;
  5. anything else under the tree -> ANCILLARY (light).

The strict §1–§10 / §11+ contract applies only to SUBSYSTEM and SINGLE; COMMON and
ANCILLARY are light; IGNORED is never touched.
"""

import fnmatch
import re

from . import io_utf8


class DocKind:
    SUBSYSTEM = "SUBSYSTEM"
    ROOT = "ROOT"
    SINGLE = "SINGLE"
    COMMON = "COMMON"
    ANCILLARY = "ANCILLARY"
    IGNORED = "IGNORED"


STRICT = (DocKind.SUBSYSTEM, DocKind.SINGLE)
LIGHT = (DocKind.COMMON, DocKind.ANCILLARY)

DEFAULT_IGNORE_GLOBS = ["issue/**", "whole_architecture.md", "spec/**", "**/.review.md"]

_IGNORE_BLOCK_RE = re.compile(r"```ignore-globs[ \t]*\r?\n(.*?)```", re.DOTALL)


def load_ignore_globs(conventions_path):
    """Read the ```ignore-globs fenced block from common-conventions.md. Lines whose
    first non-space char is ``#`` are comments; blank lines are skipped."""
    try:
        text = io_utf8.read_text(conventions_path)
    except Exception:
        return list(DEFAULT_IGNORE_GLOBS)
    m = _IGNORE_BLOCK_RE.search(text)
    if not m:
        return list(DEFAULT_IGNORE_GLOBS)
    globs = []
    for line in m.group(1).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        globs.append(stripped)
    return globs or list(DEFAULT_IGNORE_GLOBS)


def _norm(rel_path):
    p = rel_path.replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p.strip("/")


def _glob_to_regex(pattern):
    # handle a leading/standalone '**/' as an optional any-prefix
    pattern = pattern.replace("**/", "\x00")
    out = []
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == "\x00":
            out.append("(?:.*/)?")
            i += 1
        elif pattern[i:i + 2] == "**":
            out.append(".*")
            i += 2
        elif ch == "*":
            out.append("[^/]*")
            i += 1
        elif ch == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(ch))
            i += 1
    return re.compile("^" + "".join(out) + "$")


def glob_match(pattern, path):
    path = _norm(path)
    if "/" not in pattern and "**" not in pattern:
        return fnmatch.fnmatch(path.split("/")[-1], pattern)
    return bool(_glob_to_regex(pattern).match(path))


def matches_any_glob(path, globs):
    return any(glob_match(g, path) for g in globs)


def _looks_like_root(text):
    if text is None:
        return True
    if re.search(r"^##[ \t]+子系统清单[ \t]*$", text, re.MULTILINE):
        return True
    # a single/subsystem doc has a numbered §1; if present and no 子系统清单, it's SINGLE
    if re.search(r"^##[ \t]+1\.", text, re.MULTILINE):
        return False
    return True


def classify(rel_path, text=None, ignore_globs=None):
    path = _norm(rel_path)
    if ignore_globs is None:
        ignore_globs = DEFAULT_IGNORE_GLOBS
    parts = path.split("/")
    first = parts[0]

    # 1. directory namespace
    if first.startswith("."):
        return DocKind.IGNORED
    if first.startswith("_"):
        return DocKind.COMMON if first == "_common" else DocKind.IGNORED

    # 2. ignore globs
    if matches_any_glob(path, ignore_globs):
        return DocKind.IGNORED

    basename = parts[-1]
    # 3. doc-root top-level
    if len(parts) == 1:
        if basename == "architecture.md":
            return DocKind.ROOT if _looks_like_root(text) else DocKind.SINGLE
        return DocKind.ANCILLARY

    # 4. <subsystem>/architecture.md
    if len(parts) == 2 and basename == "architecture.md":
        return DocKind.SUBSYSTEM

    # 5. everything else under the tree
    return DocKind.ANCILLARY
