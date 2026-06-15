"""Stable question IDs (plan §6.3).

``q_`` + sha1( doc-rel-path ‖ [§位置]规范化 ‖ 疑问首句规范化 )[:8]

The id is derived from CONTENT, not position, so deleting an earlier entry does not
renumber later ones. The "已检查 / 建议核实方向" tail is NOT hashed (it changes during a
partial-resolve, but the entry is still the same question), the locator IS hashed (moving
the question to another section is a different question), and the doc path IS hashed (the
same text in two docs gets two ids). An explicit persistent id written into the first
sentence (e.g. ``PD-LIN-003``) is naturally included and only stabilises the hash further.

These ids are session-local handles: every round recomputes them from current content via
``enumerate_questions``; matching is by recomputed id, so a stale id simply fails to match
(E_ADDR_NOTFOUND) and never edits the wrong entry.
"""

import hashlib
import re
import unicodedata

from .model import QuestionEntry
from . import parser

SEP = "‖"  # ‖


def _normalize(s):
    s = unicodedata.normalize("NFC", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def compute_qid(doc_rel_path, locator, first_sentence):
    rel = doc_rel_path.replace("\\", "/")
    raw = SEP.join([rel, _normalize(locator), _normalize(first_sentence)])
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8]
    return "q_" + digest


def _extract_locator_and_first(item_text):
    lb = item_text.find("[")
    rb = item_text.find("]", lb + 1) if lb >= 0 else -1
    if lb >= 0 and rb > lb:
        locator = item_text[lb + 1:rb]
        after = item_text[rb + 1:]
    else:
        locator = ""
        after = item_text.lstrip(" -\t")
    dot = after.find("。")  # 。
    first = after[:dot] if dot >= 0 else after
    first = first.strip(" -\t\r\n")
    return locator, first


def _question_section(doc):
    s = doc.section_by_number("10")
    if s is not None:
        return s
    for sec in doc.sections:
        if sec.title.startswith("待确认"):
            return sec
    return None


def enumerate_questions(doc_rel_path, doc):
    sec = _question_section(doc)
    if sec is None:
        return []
    entries = []
    for start, end, raw in parser.list_items_in(doc.text, sec.body_start, sec.end):
        locator, first = _extract_locator_and_first(raw)
        qid = compute_qid(doc_rel_path, locator, first)
        entries.append(QuestionEntry(
            raw=raw, start=start, end=end,
            locator=_normalize(locator), first_sentence=_normalize(first), qid=qid))
    return entries


def find_question(doc_rel_path, doc, qid):
    for e in enumerate_questions(doc_rel_path, doc):
        if e.qid == qid:
            return e
    return None
