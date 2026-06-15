"""Structural addressing — resolve an ``at`` block to a node span, never by line
number (plan §6.4).

``at`` fields:
  section      top-level chapter number, e.g. "6", "7"  (required)
  entry        §6 entry: a number ("6.6") or an identifier substring ("OTA")
  subsection   "处理流程"/"数据交互" (H4 under a §6 entry) or "7.1" (a §7 sub-table)
  anchor_mode  replace | append | append_table_row

Failures: 0 hits -> E_ADDR_NOTFOUND; an identifier ``entry`` hitting >=2 -> E_ADDR_AMBIGUOUS.
A ``replace`` carrying a ``replace_match`` whose bytes are not found verbatim -> E_MATCH_STALE.
"""

import re

from .errors import AddressNotFound, AddressAmbiguous, MatchStale, UsageError
from .model import Edit
from . import parser

_NUMERIC_RE = re.compile(r"^\d+(?:\.\d+)*$")


class Target:
    def __init__(self, heading, body_start, end, level):
        self.heading = heading          # the resolved node's heading (None only at doc level)
        self.body_start = body_start    # offset just past the heading line
        self.end = end                  # node block end (next same-or-higher heading / section end)
        self.level = level


def _node_end(doc, heading, cap):
    """End of a heading's own block: the next heading whose level <= this heading's,
    capped at ``cap``."""
    best = cap
    for k in doc.headings:
        if k.line_start > heading.line_start and k.level <= heading.level:
            if k.line_start < best:
                best = k.line_start
            break  # headings are in document order; first qualifying one wins
    return best


def resolve(doc, at):
    section_no = at.get("section")
    if section_no is None:
        raise UsageError("寻址缺少 section 字段", code="E_USAGE")
    section = doc.section_by_number(str(section_no))
    if section is None:
        raise AddressNotFound("找不到章节 §{}".format(section_no),
                              detail={"section": section_no})

    target = Target(section.heading, section.body_start, section.end, 2)

    entry = at.get("entry")
    if entry is not None:
        target = _resolve_entry(doc, section, str(entry))

    subsection = at.get("subsection")
    if subsection is not None:
        target = _resolve_subsection(doc, section, target, str(subsection))

    return target


def _resolve_entry(doc, section, entry):
    if _NUMERIC_RE.match(entry):
        matches = [c for c in section.children if c.number == entry]
    else:
        matches = [c for c in section.children
                   if c.level == 3 and entry in c.title]
    if not matches:
        raise AddressNotFound("§{} 下找不到入口 {}".format(section.number, entry),
                              detail={"section": section.number, "entry": entry})
    if len(matches) > 1:
        raise AddressAmbiguous(
            "§{} 下入口 {} 命中 {} 个，请改用编号形式".format(section.number, entry, len(matches)),
            detail={"section": section.number, "entry": entry, "hits": len(matches)})
    h = matches[0]
    return Target(h, h.line_end, _node_end(doc, h, section.end), h.level)


def _resolve_subsection(doc, section, parent, subsection):
    if _NUMERIC_RE.match(subsection):
        matches = [c for c in section.children if c.number == subsection]
    else:
        # an H4 sub-node whose title matches, inside the parent node's block
        matches = [c for c in section.children
                   if c.title == subsection
                   and parent.body_start <= c.line_start < parent.end]
    if not matches:
        raise AddressNotFound(
            "§{} 下找不到子节 {}".format(section.number, subsection),
            detail={"section": section.number, "subsection": subsection})
    if len(matches) > 1:
        raise AddressAmbiguous(
            "§{} 下子节 {} 命中 {} 个".format(section.number, subsection, len(matches)),
            detail={"section": section.number, "subsection": subsection, "hits": len(matches)})
    h = matches[0]
    return Target(h, h.line_end, _node_end(doc, h, section.end), h.level)


def _append_position(text, body_start, end):
    """Insert point = just after the last non-blank line in [body_start, end), so new
    content sits adjacent to existing content, before any trailing blank lines / next
    heading."""
    pos = body_start
    last = body_start
    for s, e in parser._line_spans(text):
        if s < body_start or s >= end:
            continue
        if parser._line_content(text, s, e).strip():
            last = e
    return last if last > body_start else end


def build_edit(doc, target, anchor_mode, content, replace_match=None):
    text = doc.text
    if anchor_mode == "replace":
        if replace_match is not None:
            region = text[target.body_start:target.end]
            idx = region.find(replace_match)
            if idx < 0:
                raise MatchStale(
                    "替换串与现文不匹配（内容已变化），拒绝基于陈旧内容修改",
                    detail={"node": _loc(target)})
            start = target.body_start + idx
            return Edit(start, start + len(replace_match), content)
        return Edit(target.body_start, target.end, content)

    if anchor_mode == "append":
        pos = _append_position(text, target.body_start, target.end)
        return Edit(pos, pos, content)

    if anchor_mode == "append_table_row":
        tables = parser.tables_in(text, target.body_start, target.end)
        if not tables:
            raise AddressNotFound("目标节点内没有表格，无法追加行", detail={"node": _loc(target)})
        table = tables[0]   # first table in the node span (consistent with ops._append_table_row)
        cells = parser.split_row(content)
        if len(cells) != table.ncols:
            raise UsageError(
                "追加行列数 {} 与表头列数 {} 不一致".format(len(cells), table.ncols),
                code="E_USAGE", detail={"want": table.ncols, "got": len(cells)})
        insert = table.rows_end
        row_text = content if content.endswith("\n") else content + "\n"
        return Edit(insert, insert, row_text)

    raise UsageError("未知 anchor_mode：{}".format(anchor_mode), code="E_USAGE")


def _loc(target):
    h = target.heading
    return h.text if h else "(doc)"
