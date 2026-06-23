"""Structural operators (plan §4 / §6.5 / §6.7).

Each handler ``op_xxx(txn, op, idx) -> OpResult`` performs the *static* part of an
operator: it resolves addressing, byte-matches replacement spans, validates schema, and
produces edits against the BASELINE text (never against an intermediate mutated state —
plan §6.5 step 3). The transaction (``txn.py``) composes the OpResults, applies the HARD
rules and the lint delta, and decides whether to write.

Operators raise the typed engine errors (``address`` / ``errors``) so the CLI can map them
to the right exit code:
    update_section / move / promote    -> AddressNotFound(4) / MatchStale(6) / UsageError(2)
    resolve_question                   -> AddressNotFound(4); coupling -> CouplingMissing(5)
    add_question                       -> UsageError(2) on a malformed entry
    update_root (mermaid_edge)         -> RootEdgeDangling(3)

OpResult fields:
    edits             list of (rel_path, Edit) against the doc's BASELINE text
    new_files         list of (abspath, rel_display, content)
    touched           set of rel/abspath strings (for the result summary)
    deletes_question  True for a resolve_question full delete
    provides_body_edit True when the op writes body content (satisfies a body_edit coupling)
    coupling          the resolve_question coupling dict, or None
"""

import os
import re

from ..errors import (
    UsageError, AddressNotFound, RootEdgeDangling,
)
from ..model import Edit
from .. import address, parser, questions


# ---------------------------------------------------------------------------
class OpResult:
    def __init__(self):
        self.edits = []                 # [(rel_path, Edit)]
        self.new_files = []             # [(abspath, rel_display, content)]
        self.touched = set()            # {rel/abspath}
        self.deletes_question = False
        self.provides_body_edit = False
        self.coupling = None

    def add_edit(self, rel_path, edit):
        self.edits.append((rel_path, edit))
        self.touched.add(rel_path)


# --- install-root / template resolution ------------------------------------
def install_root(txn):
    """The ``document-systems`` install dir; templates live at
    ``<install>/references/templates/``. ``txn.install_root`` overrides the default
    (which is computed from this package's location: wiki_engine -> scripts ->
    document-systems)."""
    if getattr(txn, "install_root", None):
        return txn.install_root
    pkg_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # wiki_engine
    return os.path.dirname(os.path.dirname(pkg_dir))                        # document-systems


_LEADING_COMMENT_RE = re.compile(r"\A<!--.*?^-->[^\n]*\n", re.DOTALL | re.MULTILINE)


def _strip_leading_comment(text):
    """Strip a leading HTML comment terminated by a standalone ``^-->`` line."""
    return _LEADING_COMMENT_RE.sub("", text, count=1)


def _ensure_trailing_newline(s):
    return s if s.endswith("\n") else s + "\n"


# ===========================================================================
# update_section
# ===========================================================================
def op_update_section(txn, op, idx):
    rel = op["target"]
    at = op["at"]
    doc = txn.baseline_doc(rel)
    content = txn.read_payload(op["content_file"])
    replace_match = None
    if op.get("replace_match_file"):
        replace_match = txn.read_payload(op["replace_match_file"])
    target = address.resolve(doc, at)
    edit = address.build_edit(doc, target, at["anchor_mode"], content, replace_match)
    res = OpResult()
    res.provides_body_edit = True
    res.add_edit(rel, edit)
    return res


# ===========================================================================
# resolve_question
# ===========================================================================
def op_resolve_question(txn, op, idx):
    rel = op["target"]
    doc = txn.baseline_doc(rel)
    qid = op["question_id"]
    entry = questions.find_question(txn.rel_key(rel), doc, qid)
    if entry is None:
        raise AddressNotFound(
            "找不到待确认条目 {}（按 baseline 内容重算 ID 未命中）".format(qid),
            detail={"target": rel, "question_id": qid})
    res = OpResult()
    res.coupling = op.get("coupling")
    mode = op.get("mode", "full")
    if mode == "full":
        res.deletes_question = True
        res.add_edit(rel, Edit(entry.start, entry.end, ""))
    elif mode == "partial":
        if not op.get("residual_file"):
            raise UsageError("resolve_question(partial) 缺少 residual_file",
                             code="E_USAGE", detail={"target": rel})
        residual = _ensure_trailing_newline(txn.read_payload(op["residual_file"]))
        res.add_edit(rel, Edit(entry.start, entry.end, residual))
    else:
        raise UsageError("resolve_question 未知 mode：{}".format(mode), code="E_USAGE")
    return res


# ===========================================================================
# add_question
# ===========================================================================
def op_add_question(txn, op, idx):
    rel = op["target"]
    doc = txn.baseline_doc(rel)
    content = txn.read_payload(op["content_file"])
    _validate_question_entry(content)
    sec = questions._question_section(doc)
    if sec is None:
        raise AddressNotFound("目标文档没有 §10 / 待确认 章节，无法新增疑问",
                              detail={"target": rel})
    body = doc.text[sec.body_start:sec.end]
    entry_text = _ensure_trailing_newline(content)
    res = OpResult()
    if body.strip() == "无":
        # replace the "无" placeholder body with the new entry
        bs = sec.body_start + body.index("无")
        res.add_edit(rel, Edit(bs, bs + len("无"), content.rstrip("\n")))
    else:
        pos = address._append_position(doc.text, sec.body_start, sec.end)
        res.add_edit(rel, Edit(pos, pos, entry_text))
    return res


def _validate_question_entry(content):
    has_loc = bool(re.search(r"\[\s*§[^\]]*\]", content))
    has_checked = "已检查" in content
    has_dir = "建议核实方向" in content
    if not (has_loc and has_checked and has_dir):
        missing = []
        if not has_loc:
            missing.append("[§位置]")
        if not has_checked:
            missing.append("已检查")
        if not has_dir:
            missing.append("建议核实方向")
        raise UsageError(
            "新增待确认条目格式不全，缺少 {}（wiki-principles §5）".format("、".join(missing)),
            code="E_USAGE", detail={"missing": missing})


# ===========================================================================
# move_with_reference
# ===========================================================================
def op_move_with_reference(txn, op, idx):
    res = OpResult()
    res.provides_body_edit = True
    for src in op["sources"]:
        _build_source_reference(txn, src, res)
    return res


def _build_source_reference(txn, src, res):
    rel = src["target"]
    doc = txn.baseline_doc(rel)
    at = src["at"]
    replace_match = txn.read_payload(src["replace_match_file"])
    reference = txn.read_payload(src["reference_text_file"])
    target = address.resolve(doc, at)
    edit = address.build_edit(doc, target, "replace", reference, replace_match)
    res.add_edit(rel, edit)


# ===========================================================================
# promote_to_common
# ===========================================================================
def op_promote_to_common(txn, op, idx):
    level = op.get("level", "repo")
    ctype = op["type"]
    common_name = op["common_name"]
    title = txn.read_payload(op["title_file"]).strip()
    body = txn.read_payload(op["body_file"]).rstrip("\n")

    # scaffold the new common doc from the template
    tpl_path = os.path.join(install_root(txn), "references", "templates",
                            "common-{}.md".format(ctype))
    from .. import io_utf8
    if not os.path.exists(tpl_path):
        raise UsageError("找不到 common 模板：common-{}.md".format(ctype),
                         code="E_USAGE", detail={"type": ctype})
    tpl = _strip_leading_comment(io_utf8.read_text(tpl_path))

    # scope sentence mentions the level + the source subsystem dir names
    src_dirs = []
    for src in op.get("sources", []):
        d = src["target"].replace("\\", "/").split("/")[0]
        if d not in src_dirs:
            src_dirs.append(d)
    level_zh = {"repo": "仓库级", "domain": "域级", "global": "全局"}.get(level, level)
    scope_body = "{}公共文档，被 {} 等子系统引用其共享事实。".format(
        level_zh, "、".join(src_dirs) if src_dirs else "本仓多个子系统")

    content = (tpl.replace("<LEVEL>", level)
                  .replace("<OWNS>", common_name)
                  .replace("<TITLE>", title)
                  .replace("<SCOPE_BODY>", scope_body)
                  .replace("<TYPE_BODY>", body)
                  .replace("<QUESTIONS>", "无"))

    abspath, rel_display = _common_target_path(txn, level, common_name)

    res = OpResult()
    res.provides_body_edit = True
    res.new_files.append((abspath, rel_display, content))
    res.touched.add(abspath)

    for src in op.get("sources", []):
        _build_source_reference(txn, src, res)
    return res


def _common_target_path(txn, level, common_name):
    """Three-level common (doc_root = <wiki_base>/<domain>/<repo>):
      repo   -> <doc_root>/_common/<name>.md            (rel ./_common/  from root doc)
      domain -> <wiki_base>/<domain>/_common/<name>.md  (rel ../_common/  from root doc)
      global -> <wiki_base>/_common/<name>.md           (rel ../../_common/ from root doc)
    Returns (abspath, rel_display).
    Callers without a real doc_root (e.g. cli.cmd_init_common) must synthesize a
    doc_root at the matching nesting depth so these dirname() levels land right."""
    fname = "{}.md".format(common_name)
    doc_root = os.path.normpath(txn.doc_root)
    if level == "global":
        base = os.path.dirname(os.path.dirname(doc_root))
        rel_display = "../../_common/{}".format(fname)
    elif level == "domain":
        base = os.path.dirname(doc_root)
        rel_display = "../_common/{}".format(fname)
    else:  # repo
        base = doc_root
        rel_display = "_common/{}".format(fname)
    abspath = os.path.normpath(os.path.join(base, "_common", fname))
    return abspath, rel_display


# ===========================================================================
# update_root (plan §6.7) — only named regions, never frontmatter / 系统架构特点 /
# numbered-drift chapters.
# ===========================================================================
def op_update_root(txn, op, idx):
    rel = op["target"]
    doc = txn.baseline_doc(rel)
    kind = op["kind"]
    action = op.get("action", "add")
    if action != "add":
        raise UsageError("update_root 暂仅支持 action=add（kind={}）".format(kind),
                         code="E_USAGE", detail={"kind": kind, "action": action})
    handler = _ROOT_KINDS.get(kind)
    if handler is None:
        raise UsageError("未知 update_root kind：{}".format(kind), code="E_USAGE")
    res = OpResult()
    handler(txn, doc, op, rel, res)
    return res


def _region_section(doc, title):
    sec = doc.section_by_title(title)
    if sec is None:
        raise AddressNotFound("根文档缺少具名区域「{}」".format(title),
                              detail={"region": title})
    return sec


def _append_table_row(doc, sec, cells, rel, res):
    tables = parser.tables_in(doc.text, sec.body_start, sec.end)
    if not tables:
        raise AddressNotFound("区域「{}」内没有表格".format(sec.title),
                              detail={"region": sec.title})
    table = tables[0]
    if len(cells) != table.ncols:
        raise UsageError(
            "行列数 {} 与表头列数 {} 不一致".format(len(cells), table.ncols),
            code="E_USAGE", detail={"want": table.ncols, "got": len(cells)})
    row = "| " + " | ".join(cells) + " |\n"
    res.add_edit(rel, Edit(table.rows_end, table.rows_end, row))


_SUBSYSTEM_COLS = ["子系统", "类型", "端口", "路径", "上游依赖", "详细文档"]


def _root_subsystem_row(txn, doc, op, rel, res):
    sec = _region_section(doc, "子系统清单")
    row = op["row"]
    name = op["name"]
    cells = [name,
             row.get("类型", "—"), row.get("端口", "—"), row.get("路径", name),
             row.get("上游依赖", "—"), row.get("详细文档", "—")]
    _append_table_row(doc, sec, cells, rel, res)


def _root_protocol_row(txn, doc, op, rel, res):
    sec = _region_section(doc, "跨系统通信方式")
    cells = op["row"] if isinstance(op["row"], list) else list(op["row"].values())
    _append_table_row(doc, sec, cells, rel, res)


def _root_aux_resource(txn, doc, op, rel, res):
    sec = _region_section(doc, "辅助资源")
    bullet = op["bullet"] if isinstance(op.get("bullet"), str) else op.get("text", "")
    if not bullet:
        raise UsageError("aux_resource 缺少 bullet/text 字段", code="E_USAGE")
    line = "- " + bullet.lstrip("- ").rstrip("\n") + "\n"
    body = doc.text[sec.body_start:sec.end]
    if body.strip() == "无":
        bs = sec.body_start + body.index("无")
        res.add_edit(rel, Edit(bs, bs + len("无"), line.rstrip("\n")))
    else:
        pos = address._append_position(doc.text, sec.body_start, sec.end)
        res.add_edit(rel, Edit(pos, pos, line))


def _fence_span(doc, sec):
    """Return (open_line_end, close_line_start) of the FIRST code fence inside the
    section's body — the mermaid fence. None if not found."""
    open_end = None
    for s, e in parser._line_spans(doc.text):
        if not (sec.body_start <= s < sec.end):
            continue
        content = parser._line_content(doc.text, s, e)
        if content.lstrip().startswith("```"):
            if open_end is None:
                open_end = e
            else:
                return open_end, s
    return None


def _root_mermaid_node(txn, doc, op, rel, res):
    sec = _region_section(doc, "依赖关系图")
    span = _fence_span(doc, sec)
    if span is None:
        raise AddressNotFound("依赖关系图区域没有完整的 mermaid 围栏", detail={"region": "依赖关系图"})
    _open_end, close_start = span
    node_id = op["node_id"]
    label = op["label"]
    line = '{}["{}"]\n'.format(node_id, label)
    res.add_edit(rel, Edit(close_start, close_start, line))


_NODE_DECL_RE = r"^\s*{}\["


def _root_mermaid_edge(txn, doc, op, rel, res):
    sec = _region_section(doc, "依赖关系图")
    span = _fence_span(doc, sec)
    if span is None:
        raise AddressNotFound("依赖关系图区域没有完整的 mermaid 围栏", detail={"region": "依赖关系图"})
    open_end, close_start = span
    fence_body = doc.text[open_end:close_start]
    src = op["from"]
    dst = op["to"]
    for node in (src, dst):
        if not re.search(_NODE_DECL_RE.format(re.escape(node)), fence_body, re.MULTILINE):
            raise RootEdgeDangling(
                "依赖边端点未在图中声明为节点：{}".format(node),
                detail={"from": src, "to": dst, "missing": node})
    line = "{} --> {}\n".format(src, dst)
    res.add_edit(rel, Edit(close_start, close_start, line))


_COMMON_LINK_PREFIX = {"repo": "./_common/", "domain": "../_common/", "global": "../../_common/"}
_COMMON_LEVEL_ZH = {"repo": "仓库级", "domain": "域级", "global": "全局"}


def _root_common_index_entry(txn, doc, op, rel, res):
    name = op["name"]
    level = op.get("level", "repo")
    prefix = _COMMON_LINK_PREFIX.get(level, "./_common/")
    level_zh = op.get("级别") or _COMMON_LEVEL_ZH.get(level, level)
    ctype = op.get("类型", "")
    desc = op.get("说明", "")
    row_cells = ["[{}]({}{}.md)".format(name, prefix, name), level_zh, ctype, desc]
    sec = doc.section_by_title("仓内公共文档")
    if sec is not None:
        _append_table_row(doc, sec, row_cells, rel, res)
        return
    # create the `## 仓内公共文档` section before `## 辅助资源`
    aux = _region_section(doc, "辅助资源")
    block = (
        "## 仓内公共文档\n\n"
        "跨层级共享、无单一属主的事实由相应级别的 `_common/` 持有"
        "（仓内 `./_common/`、域内 `../_common/`、全局 `../../_common/`）；"
        "子系统文档以锚点引用、不复制其内部细节。\n\n"
        "| 公共文档 | 级别 | 类型 | 说明 |\n"
        "|---|---|---|---|\n"
        "| " + " | ".join(row_cells) + " |\n\n"
    )
    res.add_edit(rel, Edit(aux.start, aux.start, block))


_ROOT_KINDS = {
    "subsystem_row": _root_subsystem_row,
    "protocol_row": _root_protocol_row,
    "aux_resource": _root_aux_resource,
    "mermaid_node": _root_mermaid_node,
    "mermaid_edge": _root_mermaid_edge,
    "common_index_entry": _root_common_index_entry,
}


# --- dispatch table --------------------------------------------------------
HANDLERS = {
    "update_section": op_update_section,
    "resolve_question": op_resolve_question,
    "add_question": op_add_question,
    "move_with_reference": op_move_with_reference,
    "promote_to_common": op_promote_to_common,
    "update_root": op_update_root,
}


def dispatch(txn, op, idx):
    name = op.get("op")
    handler = HANDLERS.get(name)
    if handler is None:
        raise UsageError("未知算子：{}".format(name), code="E_USAGE", detail={"op": name})
    return handler(txn, op, idx)
