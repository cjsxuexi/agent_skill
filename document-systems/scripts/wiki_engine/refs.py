"""Live reverse-reference computation (plan §6.2 refs, §9.1).

Never writes an index file — "who links to X" is computed on demand by walking the scope
root and resolving every markdown link, so there is nothing to drift (wiki-principles §7).
"""

import os

from . import io_utf8, parser, doc_kind


def _iter_md_files(scope_root):
    for root, dirs, files in os.walk(scope_root):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in files:
            if f.endswith(".md"):
                yield os.path.join(root, f)


def compute_refs(target_path, scope_root, anchor=None):
    """Return referrers to ``target_path`` (optionally a specific ``anchor``) found under
    ``scope_root``. Each item: {referrer, anchor}."""
    target_abs = os.path.normpath(os.path.abspath(target_path))
    out = []
    for md in _iter_md_files(scope_root):
        rel = os.path.relpath(md, scope_root).replace("\\", "/")
        # skip ignored docs as referrers (they are not governed)
        if doc_kind.classify(rel) == doc_kind.DocKind.IGNORED:
            continue
        try:
            text = io_utf8.read_text(md)
        except Exception:
            continue
        doc = parser.parse(md, text)
        md_dir = os.path.dirname(md)
        for link in doc.links:
            if not link.target.endswith(".md"):
                continue
            link_abs = os.path.normpath(os.path.join(md_dir, link.target))
            if link_abs != target_abs:
                continue
            if anchor is not None and link.anchor != anchor:
                continue
            out.append({"referrer": rel, "anchor": link.anchor})
    return out
