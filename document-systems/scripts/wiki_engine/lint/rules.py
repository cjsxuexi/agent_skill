"""Lint rules. Every rule cites the contract clause it enforces (MAINTAINER §10
Direction A); clauses that genuinely need an LLM are registered with ``llm_only=True``
and a checker that returns nothing (MAINTAINER §10 Direction B). The full table is emitted
by ``rule-catalog``.
"""

import os
import re

from .base import (
    Rule, LintContext, ERROR, WARN, INFO, HARD, DELTA, NEVER,
)
from .. import parser, io_utf8

# DocKind strings (kept literal to avoid importing the enum container here)
SUBSYSTEM, ROOT, SINGLE, COMMON, ANCILLARY = "SUBSYSTEM", "ROOT", "SINGLE", "COMMON", "ANCILLARY"
STRICT = (SUBSYSTEM, SINGLE)

CANONICAL_TITLES = {
    "1": "概述", "2": "入口与启动", "3": "目录结构", "4": "对外接口", "5": "上下游依赖",
    "6": "业务流", "7": "数据资产", "8": "关键配置项", "9": "已知问题 / 历史决定",
    "10": "待确认 / 疑问",
}
SPEC_WORDS = ["可能", "似乎", "推测", "估计", "应该是"]
COMMON_TYPES = {"glossary", "shared-lib", "protocol", "infra"}
COMMON_LEVELS = {"repo", "global"}
DERIVED_RE = re.compile(r"(^\.[^/]*\.md$)|(\.(changes|questions|history|index|assets-index|prev|refine-log)\.md$)")
# A line-number anchor is `:L<n>` anywhere, or `<file>.<ext>:<n>` with the colon
# IMMEDIATELY after the extension (so config like `bootstrap.yml ... nacos:8848` is NOT
# mistaken for a line ref).
LINENO_RE = re.compile(r":L\d+|\.(?:java|kt|ts|py|xml|sql|yml|yaml|js):\d+")
SKIP_DIRS = {"node_modules", "target", "dist", "build", ".git", ".idea", "out",
             "__pycache__", ".venv", "venv", ".gradle"}
SOURCE_EXTS = {".java", ".kt", ".ts", ".py", ".yml", ".yaml", ".xml", ".sql", ".js",
               ".json", ".properties"}


# --- small helpers --------------------------------------------------------
def _top_int(number):
    try:
        return int(str(number).split(".")[0])
    except (ValueError, AttributeError):
        return None


def _section_at(doc, offset):
    for s in doc.sections:
        if s.start <= offset < s.end:
            return s
    return None


def _body(doc, section):
    return doc.text[section.body_start:section.end]


def _question_section(doc):
    s = doc.section_by_number("10")
    if s is not None:
        return s
    for sec in doc.sections:
        if sec.title.startswith("待确认"):
            return sec
    return None


# --- structure ------------------------------------------------------------
def check_no_section_11plus(ctx):
    out = []
    for s in ctx.doc.sections:
        n = _top_int(s.number)
        if n is not None and n >= 11:
            out.append(ctx.make(R_NO_11PLUS, ERROR,
                                "strict 文档禁止 §11+：发现 ## {} {}".format(s.number, s.title),
                                "§{}".format(s.number)))
    return out


def check_sections_1_10(ctx):
    out = []
    present = {}
    seq = []
    for s in ctx.doc.sections:
        n = _top_int(s.number)
        if n is not None and 1 <= n <= 10 and "." not in str(s.number):
            present[n] = s
            seq.append(n)
    for n in range(1, 11):
        if n not in present:
            out.append(ctx.make(R_SECTIONS_1_10, ERROR,
                                "缺少 §{} {}".format(n, CANONICAL_TITLES[str(n)]),
                                "§{}".format(n)))
    ordered = [n for n in seq]
    if ordered != sorted(ordered):
        out.append(ctx.make(R_SECTIONS_1_10, ERROR,
                            "§1–§10 顺序错乱：{}".format(ordered), "order"))
    return out


def check_title_canonical(ctx):
    out = []
    for s in ctx.doc.sections:
        if s.number in CANONICAL_TITLES and s.title != CANONICAL_TITLES[s.number]:
            out.append(ctx.make(R_TITLE_CANON, INFO,
                                "§{} 标题为「{}」，规范为「{}」（仅提示，不阻塞）".format(
                                    s.number, s.title, CANONICAL_TITLES[s.number]),
                                "§{}".format(s.number)))
    return out


def check_6_double_subsection(ctx):
    out = []
    s6 = ctx.doc.section_by_number("6")
    if s6 is None:
        return out
    entries = [c for c in s6.children if c.level == 3 and c.number and c.number.startswith("6.")]
    for i, e in enumerate(entries):
        # the entry's block ends at the NEXT level-3 entry (not the next child, which is
        # this entry's own ####  6.x.1 处理流程 sub-heading).
        block_end = entries[i + 1].line_start if i + 1 < len(entries) else s6.end
        titles = [c.title for c in s6.children
                  if c.level >= 4 and e.line_start < c.line_start < block_end]
        for need in ("处理流程", "数据交互"):
            if need not in titles:
                out.append(ctx.make(R_6_DOUBLE, WARN,
                                    "§{} 缺少子节「{}」(code-wiki-conventions §4)".format(e.number, need),
                                    "§{}".format(e.number)))
    return out


def check_7_six_tables(ctx):
    out = []
    s7 = ctx.doc.section_by_number("7")
    if s7 is None:
        return out
    present = {c.number for c in s7.children if c.number and c.number.startswith("7.")}
    for i in range(1, 7):
        num = "7.{}".format(i)
        if num not in present:
            out.append(ctx.make(R_7_TABLES, WARN,
                                "§7 缺少子表 {}（未用渠道也应写 无，code-wiki-conventions §6）".format(num),
                                num))
    return out


# --- anchors --------------------------------------------------------------
def check_anchor_no_lineno(ctx):
    out = []
    for m in LINENO_RE.finditer(ctx.doc.text):
        sec = _section_at(ctx.doc, m.start())
        pos = "§{}".format(sec.number) if sec and sec.number else "doc"
        out.append(ctx.make(R_ANCHOR_LINENO, ERROR,
                            "锚点含行号：`{}`（应为 Class#method (path)，wiki-principles §2）".format(
                                m.group(0)),
                            pos))
    return out


# --- links ----------------------------------------------------------------
def _md_link(link):
    return link.target.endswith(".md")


def check_link_target_exists(ctx):
    out = []
    if ctx.doc_root is None:
        return out
    for link in ctx.doc.links:
        if not _md_link(link):
            continue
        abspath = ctx.resolve_link_path(link.target)
        if abspath and ctx.link_exists(link.target) is False:
            sec = _section_at(ctx.doc, link.start)
            pos = "§{}".format(sec.number) if sec and sec.number else "doc"
            out.append(ctx.make(R_LINK_TARGET, ERROR,
                                "跨文档链接目标不存在：{}".format(link.target), pos))
    return out


def check_link_anchor_resolves(ctx):
    out = []
    if ctx.doc_root is None:
        return out
    for link in ctx.doc.links:
        if not _md_link(link) or not link.anchor:
            continue
        anchors = ctx.target_anchors(link.target)
        if anchors is None:
            continue  # missing file handled by R_LINK_TARGET
        if link.anchor not in anchors:
            sec = _section_at(ctx.doc, link.start)
            pos = "§{}".format(sec.number) if sec and sec.number else "doc"
            out.append(ctx.make(R_LINK_ANCHOR, ERROR,
                                "跨文档锚点失效：{}#{}（目标无此标题）".format(link.target, link.anchor),
                                pos))
    return out


def check_link_crossdoc_needs_anchor(ctx):
    out = []
    for link in ctx.doc.links:
        if not _md_link(link):
            continue
        if ("/" in link.target or ".." in link.target) and not link.anchor:
            sec = _section_at(ctx.doc, link.start)
            pos = "§{}".format(sec.number) if sec and sec.number else "doc"
            out.append(ctx.make(R_LINK_NEEDS_ANCHOR, WARN,
                                "跨文档链接缺锚点：{}（wiki-principles §4）".format(link.target), pos))
    return out


def check_link_derived_file(ctx):
    out = []
    for link in ctx.doc.links:
        base = link.target.replace("\\", "/").split("/")[-1]
        if DERIVED_RE.search(base):
            sec = _section_at(ctx.doc, link.start)
            pos = "§{}".format(sec.number) if sec and sec.number else "doc"
            out.append(ctx.make(R_LINK_DERIVED, ERROR,
                                "禁止链接派生文件：{}（wiki-principles §7）".format(link.target), pos))
    return out


# --- speculation / §10 ----------------------------------------------------
def check_no_speculation(ctx):
    out = []
    if ctx.doc_kind in STRICT:
        targets = [s for s in ctx.doc.sections
                   if _top_int(s.number) is not None and 1 <= _top_int(s.number) <= 9
                   and "." not in str(s.number)]
    else:  # COMMON
        qsec = _question_section(ctx.doc)
        targets = [s for s in ctx.doc.sections if s is not qsec]
    for s in targets:
        body = _body(ctx.doc, s)
        for w in SPEC_WORDS:
            if w in body:
                out.append(ctx.make(R_SPEC, ERROR,
                                    "§{} 出现臆测词「{}」，应移入待确认 (wiki-principles §5)".format(
                                        s.number or s.title, w),
                                    "§{}".format(s.number or s.title)))
                break
    return out


def check_q10_format(ctx):
    out = []
    sec = _question_section(ctx.doc)
    if sec is None:
        if ctx.doc_kind in STRICT:
            out.append(ctx.make(R_Q10, ERROR, "缺少 §10 待确认 / 疑问 (wiki-principles §5)", "§10"))
        return out
    for i, (s, e, raw) in enumerate(parser.list_items_in(ctx.doc.text, sec.body_start, sec.end)):
        has_loc = "[" in raw and "]" in raw and "§" in raw.split("]")[0]
        has_checked = "已检查" in raw
        has_dir = "建议核实方向" in raw
        if not (has_loc and has_checked and has_dir):
            missing = []
            if not has_loc:
                missing.append("[§位置]")
            if not has_checked:
                missing.append("已检查")
            if not has_dir:
                missing.append("建议核实方向")
            out.append(ctx.make(R_Q10, ERROR,
                                "待确认条目格式不全，缺少 {}（wiki-principles §5）".format("、".join(missing)),
                                "{}#{}".format(sec.number or "待确认", i)))
    return out


# --- data names (hybrid; needs source) ------------------------------------
def _source_blob(ctx):
    cache = getattr(ctx, "_source_blob", None)
    if cache is not None:
        return cache
    parts = []
    for root, dirs, files in os.walk(ctx.source_root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if os.path.splitext(f)[1].lower() in SOURCE_EXTS:
                try:
                    parts.append(io_utf8.read_text(os.path.join(root, f)))
                except Exception:
                    pass
    blob = "\n".join(parts)
    ctx._source_blob = blob
    return blob


def _data_names(doc):
    """Backticked names in §7 sub-table first columns (the canonical asset registry)."""
    s7 = doc.section_by_number("7")
    if s7 is None:
        return []
    names = []
    for tbl in parser.tables_in(doc.text, s7.body_start, s7.end):
        # rows after header + delimiter
        for s, e in parser._line_spans(doc.text):
            if not (tbl.start <= s < tbl.end):
                continue
            line = parser._line_content(doc.text, s, e)
            if not line.lstrip().startswith("|"):
                continue
            cells = parser.split_row(line)
            if not cells:
                continue
            first = cells[0]
            if first in ("---", "") or set(first) <= {"-", " "}:
                continue
            for tok in re.findall(r"`([^`]+)`", first):
                if "用户口述" in line:
                    continue
                names.append(tok)
    return names


def check_data_name_grep(ctx):
    if not ctx.source_root:
        return [ctx.make(R_DATA_GREP, WARN,
                         "数据名 grep 校验已跳过（未提供 --source-root）", "data-names")]
    out = []
    blob = _source_blob(ctx)
    for name in _data_names(ctx.doc):
        core = re.split(r"[{}]", name)[0].strip()
        if len(core) < 3:
            continue
        if core not in blob:
            out.append(ctx.make(R_DATA_GREP, ERROR,
                                "数据名源码不可 grep：`{}`（code-wiki-conventions §8）".format(name),
                                name))
    return out


# --- ownership (LLM-only) -------------------------------------------------
def check_ownership(ctx):
    # Whether another subsystem's identifier is a cross-system contract or an
    # implementation-detail leak is a semantic call (MAINTAINER §10 Direction B).
    # The engine deliberately has no mechanical rule here; the verdict is the LLM's.
    return []


# --- root -----------------------------------------------------------------
def check_root_numbered_chapter(ctx):
    out = []
    for s in ctx.doc.sections:
        if _top_int(s.number) is not None:
            out.append(ctx.make(R_ROOT_NUMBERED, WARN,
                                "根文档不应出现带编号章节 ## {}.（体系外漂移，update_root 不碰）".format(s.number),
                                "§{}".format(s.number)))
    return out


def check_root_mermaid_balanced(ctx):
    fences = 0
    for s, e in parser._line_spans(ctx.doc.text):
        if parser._line_content(ctx.doc.text, s, e).lstrip().startswith("```"):
            fences += 1
    if fences % 2 != 0:
        return [ctx.make(R_ROOT_MERMAID, WARN, "代码围栏未闭合（mermaid 浅检查）", "mermaid")]
    return []


# --- common ---------------------------------------------------------------
def check_common_frontmatter(ctx):
    out = []
    fm = ctx.doc.frontmatter
    if fm.kind != "yaml":
        return [ctx.make(R_COMMON_FM, ERROR, "common 文档缺少 YAML frontmatter (common-conventions §7)",
                         "frontmatter")]
    ct = fm.data.get("common_type")
    lv = fm.data.get("level")
    ow = fm.data.get("owns")
    if ct not in COMMON_TYPES:
        out.append(ctx.make(R_COMMON_FM, ERROR,
                            "common_type 非法或缺失：{}（须为 {}）".format(ct, "/".join(sorted(COMMON_TYPES))),
                            "frontmatter"))
    if lv not in COMMON_LEVELS:
        out.append(ctx.make(R_COMMON_FM, ERROR,
                            "level 非法或缺失：{}（须为 repo/global）".format(lv), "frontmatter"))
    if not ow:
        out.append(ctx.make(R_COMMON_FM, ERROR, "owns 缺失（common-conventions §7）", "frontmatter"))
    return out


def check_common_skeleton(ctx):
    out = []
    titles = [s.title for s in ctx.doc.sections]
    has_scope = any(t == "范围与级别" for t in titles) or ctx.doc.section_by_number("1") is not None
    has_tail = any(t.startswith("待确认") for t in titles)
    if not has_scope:
        out.append(ctx.make(R_COMMON_SKEL, WARN, "common 文档缺少「## 1. 范围与级别」(common-conventions §5)",
                            "skeleton"))
    if not has_tail:
        out.append(ctx.make(R_COMMON_SKEL, WARN, "common 文档缺少「## 待确认 / 疑问」(common-conventions §5)",
                            "skeleton"))
    return out


# --- registry -------------------------------------------------------------
R_NO_11PLUS = Rule("STRUCT_NO_SECTION_11PLUS", "wiki-principles §1 / refine 禁 §11+",
                   ERROR, HARD, STRICT, check_no_section_11plus,
                   description="strict 文档禁止 §11+ 章节")
R_SECTIONS_1_10 = Rule("STRUCT_SECTIONS_1_10", "wiki-principles §1", ERROR, DELTA, STRICT,
                       check_sections_1_10, description="§1–§10 在位有序")
R_TITLE_CANON = Rule("STRUCT_TITLE_CANONICAL", "subsystem-prompt 章节名", INFO, NEVER, STRICT,
                     check_title_canonical, description="章节标题字面（概览≠概述，仅提示）")
R_6_DOUBLE = Rule("STRUCT_6_DOUBLE_SUBSECTION", "code-wiki-conventions §4", WARN, DELTA, STRICT,
                  check_6_double_subsection, description="§6 入口双子节 处理流程 + 数据交互")
R_7_TABLES = Rule("STRUCT_7_SIX_TABLES", "code-wiki-conventions §6", WARN, DELTA, STRICT,
                  check_7_six_tables, description="§7 六张反查子表")
R_ANCHOR_LINENO = Rule("ANCHOR_NO_LINENO", "wiki-principles §2", ERROR, DELTA,
                       (SUBSYSTEM, SINGLE, ROOT, COMMON, ANCILLARY), check_anchor_no_lineno,
                       description="锚点禁止行号")
R_LINK_TARGET = Rule("LINK_TARGET_EXISTS", "wiki-principles §4", ERROR, DELTA,
                     (SUBSYSTEM, SINGLE, ROOT, COMMON, ANCILLARY), check_link_target_exists,
                     description="跨文档链接目标文件存在")
R_LINK_ANCHOR = Rule("LINK_ANCHOR_RESOLVES", "wiki-principles §4 / §2 slug", ERROR, DELTA,
                     (SUBSYSTEM, SINGLE, ROOT, COMMON, ANCILLARY), check_link_anchor_resolves,
                     description="跨文档锚点可解析（GitHub-exact slug）")
R_LINK_NEEDS_ANCHOR = Rule("LINK_CROSSDOC_NEEDS_ANCHOR", "wiki-principles §4", WARN, DELTA,
                           (SUBSYSTEM, SINGLE, ROOT, COMMON, ANCILLARY),
                           check_link_crossdoc_needs_anchor, description="跨文档链接须带锚点")
R_LINK_DERIVED = Rule("LINK_DERIVED_FILE", "wiki-principles §7", ERROR, HARD,
                      (SUBSYSTEM, SINGLE, ROOT, COMMON, ANCILLARY), check_link_derived_file,
                      description="禁止指向派生文件的链接")
R_SPEC = Rule("SPEC_NO_SPECULATION", "wiki-principles §5", ERROR, DELTA,
              (SUBSYSTEM, SINGLE, COMMON), check_no_speculation,
              description="正文禁臆测词，不确定入待确认")
R_Q10 = Rule("Q10_FORMAT", "wiki-principles §5", ERROR, DELTA, (SUBSYSTEM, SINGLE, COMMON),
             check_q10_format, description="待确认条目格式")
R_DATA_GREP = Rule("DATA_NAME_GREP", "code-wiki-conventions §8", ERROR, DELTA, STRICT,
                   check_data_name_grep, needs_source=True,
                   description="数据名源码可 grep（需 --source-root，缺则跳过+WARN）")
R_OWNERSHIP = Rule("OWNERSHIP_FOREIGN_IDENTIFIER", "wiki-principles §3", WARN, NEVER, (SUBSYSTEM,),
                   check_ownership, llm_only=True,
                   description="跨系统契约 vs 实现泄漏由 LLM 裁决（此处无引擎规则是故意的）")
R_ROOT_NUMBERED = Rule("ROOT_NUMBERED_CHAPTER", "templates/root-architecture.md 具名区域", WARN, DELTA,
                       (ROOT,), check_root_numbered_chapter, description="根文档无带编号章节")
R_ROOT_MERMAID = Rule("ROOT_MERMAID_BALANCED", "templates/root-architecture.md 依赖关系图", WARN, DELTA,
                      (ROOT,), check_root_mermaid_balanced, description="mermaid 围栏闭合（浅检查）")
R_COMMON_FM = Rule("COMMON_FRONTMATTER", "common-conventions §7", ERROR, DELTA, (COMMON,),
                   check_common_frontmatter, description="common frontmatter 合法")
R_COMMON_SKEL = Rule("COMMON_SKELETON", "common-conventions §5", WARN, DELTA, (COMMON,),
                     check_common_skeleton, description="common 三节薄骨架")

RULES = [
    R_NO_11PLUS, R_SECTIONS_1_10, R_TITLE_CANON, R_6_DOUBLE, R_7_TABLES,
    R_ANCHOR_LINENO, R_LINK_TARGET, R_LINK_ANCHOR, R_LINK_NEEDS_ANCHOR, R_LINK_DERIVED,
    R_SPEC, R_Q10, R_DATA_GREP, R_OWNERSHIP,
    R_ROOT_NUMBERED, R_ROOT_MERMAID, R_COMMON_FM, R_COMMON_SKEL,
]
