"""Surgical render: apply recorded edits to the original text, splicing only the
edited spans (plan §3 约束 2, §6.1).

An unedited document renders to its original text exactly (the byte-exact round-trip
gate). Edits are expressed as ``(start, end, replacement)`` against the ORIGINAL text;
render sorts them, verifies they do not overlap, and splices once. Expressing every op's
change against the original (never against an intermediate mutated state) is what lets a
multi-op transaction compose without offset drift (plan §6.5 step 3 is satisfied by
single-pass application).
"""

from .errors import EngineError


def render(doc):
    """Return the document text with all recorded edits applied."""
    return apply_edits(doc.text, doc.edits)


def apply_edits(text, edits):
    if not edits:
        return text
    ordered = sorted(edits, key=lambda e: (e.start, e.end))
    out = []
    pos = 0
    for e in ordered:
        if e.start < pos:
            raise EngineError(
                "内部错误：编辑区间重叠（{}-{} 与已应用到 {}）".format(e.start, e.end, pos),
                code="E_EDIT_OVERLAP",
            )
        if e.start > len(text) or e.end > len(text) or e.start > e.end:
            raise EngineError(
                "内部错误：编辑区间越界（{}-{}，文本长度 {}）".format(e.start, e.end, len(text)),
                code="E_EDIT_RANGE",
            )
        out.append(text[pos:e.start])
        out.append(e.replacement)
        pos = e.end
    out.append(text[pos:])
    return "".join(out)
