"""Document model with byte (character) offsets (plan §6.1).

Every structural node records ``(start, end)`` character offsets into the document's
original text. ``render`` only replaces the spans of edited nodes; all other bytes are
copied verbatim, which is what makes ``render(parse(x)) == x`` hold and keeps git diffs
surgical (plan §3 约束 2).

Offsets are character offsets into the decoded ``str``. Because ``io_utf8`` always
decodes/encodes UTF-8 with no newline translation, character-exact reconstruction of the
str is byte-exact reconstruction of the file.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict


@dataclass
class Frontmatter:
    kind: str           # "yaml" | "blockquote" | "none"
    start: int
    end: int            # offset just past the frontmatter block (incl. trailing newline)
    data: Dict[str, str] = field(default_factory=dict)


@dataclass
class Heading:
    level: int          # 1..6 (number of leading '#')
    text: str           # inner text, leading/trailing spaces and trailing '#'s stripped
    number: Optional[str]   # dotted section number if the text begins with one, e.g. "6", "6.6"
    title: str          # text with the leading number stripped (== text when number is None)
    anchor: str         # GitHub-exact, de-duplicated slug of `text`
    line_start: int     # offset at the '#'
    line_end: int       # offset just past the trailing newline (or EOF)
    text_end: int       # offset just past the heading text (before any trailing newline)


@dataclass
class Table:
    start: int          # offset at the first '|' of the header row line
    end: int            # offset just past the last row line's newline
    header_cells: List[str]
    ncols: int
    row_count: int      # data rows (excluding header + delimiter)
    rows_end: int       # offset where new rows should be appended (== end)


@dataclass
class QuestionEntry:
    raw: str            # the full entry text (may span continuation lines)
    start: int
    end: int            # offset just past the entry (incl. trailing newline)
    locator: str        # the "[§...]" locator label, normalized text inside the brackets
    first_sentence: str # core question, up to the first 。 after the locator
    qid: str            # stable q_ id (filled by questions.py)


@dataclass
class Section:
    """A top-level chapter: a level-2 heading and everything until the next level-2
    heading (or EOF). Sections tile the post-preamble document exactly."""
    heading: Heading
    number: Optional[str]
    title: str
    anchor: str
    start: int          # == heading.line_start
    body_start: int     # == heading.line_end
    end: int            # next section's start, or len(text)
    children: List[Heading] = field(default_factory=list)  # level >=3 headings inside


@dataclass
class Link:
    text: str
    target: str         # the part before '#'
    anchor: Optional[str]
    start: int
    end: int


@dataclass
class Document:
    path: str
    text: str
    frontmatter: Frontmatter
    headings: List[Heading]
    sections: List[Section]
    preamble_end: int   # offset where the first level-2 section starts (or len(text))
    links: List[Link]
    doc_kind: Optional[str] = None
    edits: List["Edit"] = field(default_factory=list)

    # --- lookup helpers -------------------------------------------------
    def section_by_number(self, number: str) -> Optional[Section]:
        for s in self.sections:
            if s.number == str(number):
                return s
        return None

    def section_by_title(self, title: str) -> Optional[Section]:
        for s in self.sections:
            if s.title == title:
                return s
        return None

    def add_edit(self, start: int, end: int, replacement: str):
        self.edits.append(Edit(start, end, replacement))


@dataclass
class Edit:
    start: int
    end: int
    replacement: str
