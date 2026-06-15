"""Drift-tolerant markdown parser (plan §6.1).

Tolerates the real drift in D:\\wiki: YAML frontmatter on the root doc, "概览" vs
"概述" titles, illegal ``## 11+`` sections, extra non-contract chapters, and §6 entry /
§7 sub-table sub-headings. Parsing never fails on drift — it records the structure and
lets ``lint`` report. Every node carries exact character offsets so ``render`` can splice
surgically and ``render(parse(x)) == x`` holds byte-for-byte.
"""

import re

from .model import (
    Document, Frontmatter, Heading, Section, Link, Table,
)
from .slug import Slugger

_HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.*)$")
_NUMBER_RE = re.compile(r"^(\d+(?:\.\d+)*)(?:\.)?[ \t]+(.*)$")
_ATX_CLOSE_RE = re.compile(r"[ \t]+#+[ \t]*$")
_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)\s]+)\)")


def _line_spans(text):
    """Yield (start, end) for each physical line; ``end`` includes the line's
    terminator (``\\n`` or ``\\r\\n``). The terminators are preserved verbatim."""
    spans = []
    i = 0
    n = len(text)
    while i < n:
        j = text.find("\n", i)
        if j == -1:
            spans.append((i, n))
            break
        spans.append((i, j + 1))
        i = j + 1
    return spans


def _line_content(text, start, end):
    """Line text with its EOL (``\\r\\n`` / ``\\n``) stripped."""
    seg = text[start:end]
    if seg.endswith("\n"):
        seg = seg[:-1]
    if seg.endswith("\r"):
        seg = seg[:-1]
    return seg


def _parse_frontmatter(text, line_spans):
    if not line_spans:
        return Frontmatter("none", 0, 0, {})
    first = _line_content(text, *line_spans[0])
    if first.strip() != "---":
        return Frontmatter("none", 0, 0, {})
    # find the closing '---'
    for idx in range(1, len(line_spans)):
        content = _line_content(text, *line_spans[idx])
        if content.strip() == "---":
            block_end = line_spans[idx][1]
            data = {}
            for k in range(1, idx):
                c = _line_content(text, *line_spans[k])
                if ":" in c:
                    key, _, val = c.partition(":")
                    data[key.strip()] = val.strip()
            return Frontmatter("yaml", 0, block_end, data)
    return Frontmatter("none", 0, 0, {})


def _heading_text(raw):
    """Strip a trailing ATX close (``## Title ##``) and surrounding spaces."""
    return _ATX_CLOSE_RE.sub("", raw).strip()


def _split_number(text):
    m = _NUMBER_RE.match(text)
    if m:
        return m.group(1), m.group(2).strip()
    return None, text


def _is_fence(content):
    s = content.lstrip()
    return s.startswith("```") or s.startswith("~~~")


def _fenced_line_starts(text, all_spans):
    """Line-start offsets that fall inside (or are) a fenced code block, so structural
    detection skips them while round-trip keeps every byte."""
    fenced = set()
    in_fence = False
    for s, e in all_spans:
        content = _line_content(text, s, e)
        if _is_fence(content):
            fenced.add(s)
            in_fence = not in_fence
            continue
        if in_fence:
            fenced.add(s)
    return fenced


def _parse_headings(text, line_spans):
    slugger = Slugger()
    headings = []
    in_fence = False
    for start, end in line_spans:
        content = _line_content(text, start, end)
        if _is_fence(content):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = _HEADING_RE.match(content)
        if not m:
            continue
        level = len(m.group(1))
        htext = _heading_text(m.group(2))
        number, title = _split_number(htext)
        anchor = slugger.slug(htext)
        headings.append(Heading(
            level=level,
            text=htext,
            number=number,
            title=title,
            anchor=anchor,
            line_start=start,
            line_end=end,
            text_end=start + len(content),
        ))
    return headings


def _build_sections(text, headings):
    """Top-level chapters = level-2 headings. Sections tile [preamble_end, len(text))
    exactly; each section's children are the level>=3 headings inside it."""
    level2 = [h for h in headings if h.level == 2]
    if not level2:
        return [], len(text)
    preamble_end = level2[0].line_start
    sections = []
    for i, h in enumerate(level2):
        end = level2[i + 1].line_start if i + 1 < len(level2) else len(text)
        children = [c for c in headings
                    if c.level >= 3 and h.line_end <= c.line_start < end]
        sections.append(Section(
            heading=h,
            number=h.number,
            title=h.title,
            anchor=h.anchor,
            start=h.line_start,
            body_start=h.line_end,
            end=end,
            children=children,
        ))
    return sections, preamble_end


def _parse_links(text):
    links = []
    for m in _LINK_RE.finditer(text):
        target = m.group(2)
        anchor = None
        if "#" in target:
            target, _, anchor = target.partition("#")
        links.append(Link(
            text=m.group(1),
            target=target,
            anchor=anchor or None,
            start=m.start(),
            end=m.end(),
        ))
    return links


def parse(path, text):
    line_spans = _line_spans(text)
    frontmatter = _parse_frontmatter(text, line_spans)
    headings = _parse_headings(text, line_spans)
    sections, preamble_end = _build_sections(text, headings)
    links = _parse_links(text)
    return Document(
        path=path,
        text=text,
        frontmatter=frontmatter,
        headings=headings,
        sections=sections,
        preamble_end=preamble_end,
        links=links,
    )


# --- shared structural utilities (used by address / ops / lint) -----------

def tables_in(text, start, end):
    """Return the Tables fully contained in [start, end). A table is a maximal run of
    consecutive lines whose trimmed content starts with '|' (header + delimiter + rows)."""
    all_spans = _line_spans(text)
    fenced = _fenced_line_starts(text, all_spans)
    line_spans = [ls for ls in all_spans if start <= ls[0] < end and ls[0] not in fenced]
    tables = []
    i = 0
    n = len(line_spans)
    while i < n:
        s0, e0 = line_spans[i]
        if _line_content(text, s0, e0).lstrip().startswith("|"):
            j = i
            while j < n and _line_content(text, *line_spans[j]).lstrip().startswith("|"):
                j += 1
            run = line_spans[i:j]
            if len(run) >= 2:  # header + delimiter at minimum
                header = _line_content(text, *run[0])
                cells = _split_row(header)
                tables.append(Table(
                    start=run[0][0],
                    end=run[-1][1],
                    header_cells=cells,
                    ncols=len(cells),
                    row_count=max(0, len(run) - 2),
                    rows_end=run[-1][1],
                ))
            i = j
        else:
            i += 1
    return tables


def _split_row(line):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    # protect escaped pipes (\|) inside cells from the split
    s = s.replace("\\|", "\x00")
    return [c.strip().replace("\x00", "\\|") for c in s.split("|")]


def split_row(line):
    return _split_row(line)


def list_items_in(text, start, end):
    """Return top-level markdown list items as (item_start, item_end, raw_text).

    An item begins at a line matching ``^- `` and continues through following lines until
    the next ``^- `` top-level item, a heading, or the section end. Trailing blank lines
    before the next item are kept with the item (so spans tile contiguously)."""
    all_spans = _line_spans(text)
    fenced = _fenced_line_starts(text, all_spans)
    line_spans = [ls for ls in all_spans if start <= ls[0] < end and ls[0] not in fenced]
    items = []
    cur_start = None
    for s0, e0 in line_spans:
        content = _line_content(text, s0, e0)
        if re.match(r"^-[ \t]+", content):
            if cur_start is not None:
                items.append((cur_start, s0, text[cur_start:s0]))
            cur_start = s0
        elif _HEADING_RE.match(content) and cur_start is not None:
            # a heading terminates the current item
            items.append((cur_start, s0, text[cur_start:s0]))
            cur_start = None
    if cur_start is not None:
        items.append((cur_start, end, text[cur_start:end]))
    return items
