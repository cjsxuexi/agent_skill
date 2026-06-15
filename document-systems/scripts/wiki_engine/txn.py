"""Transaction pipeline (plan §6.5).

Load -> static-validate (inside op handlers) -> in-memory apply -> HARD rules ->
lint-delta -> write all or write nothing. Validation and lint happen BEFORE any write,
so a rejected transaction leaves the disk byte-identical (atomic; no partial writes).

Addressing handles that resolve by content (``question_id``) are matched against the
BASELINE snapshot, never an intermediate mutated state (plan §6.5 step 2). Edits are
expressed against each doc's baseline text and composed by ``render.apply_edits`` in a
single pass, which detects overlaps.
"""

import os

from . import io_utf8, parser, render, doc_kind, ops
from .errors import (
    EngineError, UsageError, CouplingMissing, TransactionRejected, ParseError,
)
from .lint import run_lint
from .lint.base import LintContext, ERROR, HARD, DELTA
from .slug import Slugger


class Transaction:
    def __init__(self, doc_root, source_root, base_dir, ops_json, install_root=None):
        self.doc_root = os.path.normpath(doc_root) if doc_root else doc_root
        self.source_root = source_root
        self.base_dir = base_dir
        self.ops = list(ops_json or [])
        self.install_root = install_root
        self._baseline_cache = {}     # rel -> Document
        self._baseline_text = {}      # rel -> str

    # --- helpers -----------------------------------------------------------
    def read_payload(self, rel):
        """Read a payload file, ``rel`` relative to ``base_dir``, UTF-8."""
        path = rel if os.path.isabs(rel) else os.path.join(self.base_dir, rel)
        return io_utf8.read_text(path)

    def rel_key(self, rel):
        """POSIX-normalized rel path (used as the qid namespace)."""
        return rel.replace("\\", "/")

    def _abspath(self, rel):
        return os.path.normpath(os.path.join(self.doc_root, rel))

    def baseline_text(self, rel):
        if rel not in self._baseline_text:
            abspath = self._abspath(rel)
            text = io_utf8.read_text_or_none(abspath)
            if text is None:
                raise ParseError("目标文档不存在：{}".format(rel), detail={"target": rel})
            self._baseline_text[rel] = text
        return self._baseline_text[rel]

    def baseline_doc(self, rel):
        if rel not in self._baseline_cache:
            text = self.baseline_text(rel)
            self._baseline_cache[rel] = parser.parse(self._abspath(rel), text)
        return self._baseline_cache[rel]

    # --- pipeline ----------------------------------------------------------
    def run(self, dry_run=False):
        # 1. run op handlers (static validation happens inside them)
        results = []
        for idx, op in enumerate(self.ops):
            results.append(ops.dispatch(self, op, idx))

        # 2. group edits per existing doc; compute new text
        edits_by_doc = {}
        for res in results:
            for rel, edit in res.edits:
                edits_by_doc.setdefault(rel, []).append(edit)

        new_text = {}
        for rel, edits in edits_by_doc.items():
            base = self.baseline_text(rel)
            try:
                new_text[rel] = render.apply_edits(base, edits)
            except EngineError as exc:
                raise TransactionRejected(
                    "文档 {} 内编辑区间冲突：{}".format(rel, exc.message_zh),
                    detail={"target": rel})

        # new files
        new_files = {}        # abspath -> (rel_display, content)
        for res in results:
            for abspath, rel_display, content in res.new_files:
                new_files[os.path.normpath(abspath)] = (rel_display, content)

        # 3. build the overlay (all pending new/edited docs) so cross-refs resolve
        overlay = {}
        for rel, text in new_text.items():
            overlay[self._abspath(rel)] = text
        for abspath, (_disp, content) in new_files.items():
            overlay[abspath] = content

        # baseline lint per touched existing doc (with overlay)
        baseline_keys = {}
        for rel in edits_by_doc:
            findings = self._lint_doc(rel, self.baseline_text(rel), overlay)
            baseline_keys[rel] = {f.key() for f in findings}

        # 4. HARD RULES — coupling for every resolve_question full op
        self._check_couplings(results)

        # 5. NEW-FINDING DELTA — lint each touched doc's NEW text + new files
        new_findings = []
        for rel, text in new_text.items():
            findings = self._lint_doc(rel, text, overlay)
            base_keys = baseline_keys.get(rel, set())
            for f in findings:
                if f.key() not in base_keys:
                    new_findings.append(f)
        for abspath, (rel_display, content) in new_files.items():
            findings = self._lint_doc_abs(abspath, content, overlay, rel_display)
            new_findings.extend(findings)  # new files: empty baseline

        blocking_new = [f for f in new_findings
                        if f.severity == ERROR and f.blocking in (HARD, DELTA)]
        if blocking_new:
            msgs = [f.message_zh for f in blocking_new]
            raise TransactionRejected(
                "事务被否决（lint 增量发现 {} 条新违规）：{}".format(len(msgs), "；".join(msgs)),
                detail={"findings": [f.to_dict() for f in blocking_new]})

        applied = sorted(edits_by_doc.keys())
        created = sorted(disp for _abs, (disp, _c) in new_files.items())

        result = {
            "status": "ok",
            "applied": applied,
            "created": created,
            "dry_run": bool(dry_run),
            "findings_new": [f.to_dict() for f in new_findings],
            "message_zh": self._summary(applied, created, dry_run),
        }

        # 6. write all-or-nothing (plan §6.5 step 6)
        if not dry_run:
            writes = [(self._abspath(rel), text) for rel, text in new_text.items()]
            writes += [(abspath, content) for abspath, (_disp, content) in new_files.items()]
            io_utf8.atomic_write_many(writes)

        return result

    # --- lint helpers ------------------------------------------------------
    def _lint_doc(self, rel, text, overlay):
        kind = self._classify(rel)
        if kind == doc_kind.DocKind.IGNORED:
            return []
        doc = parser.parse(self._abspath(rel), text)
        ctx = LintContext(self.rel_key(rel), doc, kind, doc_root=self.doc_root,
                          source_root=self.source_root, overlay=overlay)
        return run_lint(ctx)

    def _lint_doc_abs(self, abspath, text, overlay, rel_display):
        # A new common file may live OUTSIDE doc_root (global `<wiki_base>/_common/`),
        # so relpath would yield `../_common/...` and misclassify as ANCILLARY. Any file
        # whose immediate parent dir is `_common` is COMMON (repo or global).
        if os.path.basename(os.path.dirname(os.path.normpath(abspath))) == "_common":
            kind = doc_kind.DocKind.COMMON
            rel = rel_display
        else:
            rel = os.path.relpath(abspath, self.doc_root).replace("\\", "/")
            kind = self._classify(rel)
        if kind == doc_kind.DocKind.IGNORED:
            return []
        doc = parser.parse(abspath, text)
        ctx = LintContext(rel, doc, kind, doc_root=self.doc_root,
                          source_root=self.source_root, overlay=overlay)
        return run_lint(ctx)

    def _classify(self, rel):
        rel_norm = self.rel_key(rel)
        text = None
        if rel in self._baseline_text:
            text = self._baseline_text[rel]
        return doc_kind.classify(rel_norm, text)

    # --- HARD coupling rule -------------------------------------------------
    def _check_couplings(self, results):
        for idx, res in enumerate(results):
            if not res.deletes_question:
                continue
            coupling = res.coupling
            if not coupling:
                raise CouplingMissing(
                    "resolve_question(full) 缺少耦合：删 §10 条目必须有正文落点或 existing-anchor 证明",
                    detail={"op_index": idx})
            kind = coupling.get("kind")
            if kind == "body_edit":
                ref = coupling.get("ref_op_index")
                if ref is None or ref < 0 or ref >= len(results) or not results[ref].provides_body_edit:
                    raise CouplingMissing(
                        "body_edit 耦合无效：ref_op_index={} 未指向有效的正文编辑算子".format(ref),
                        detail={"op_index": idx, "ref_op_index": ref})
            elif kind == "existing_anchor":
                anchor = coupling.get("anchor")
                if not anchor or not self._anchor_exists(anchor):
                    raise CouplingMissing(
                        "existing_anchor 耦合无效：锚点 {} 不可解析".format(anchor),
                        detail={"op_index": idx, "anchor": anchor})
            else:
                raise CouplingMissing(
                    "未知耦合类型：{}".format(kind),
                    detail={"op_index": idx, "kind": kind})

    def _anchor_exists(self, spec):
        """``rel#anchor`` -> the doc's GitHub-slug heading anchors must contain anchor."""
        if "#" not in spec:
            return False
        rel, _, anchor = spec.partition("#")
        try:
            doc = self.baseline_doc(rel)
        except EngineError:
            return False
        slugger = Slugger()
        anchors = {slugger.slug(h.text) for h in doc.headings}
        return anchor in anchors

    # --- summary -----------------------------------------------------------
    def _summary(self, applied, created, dry_run):
        prefix = "预演（零写入）：" if dry_run else "已应用："
        parts = []
        if applied:
            parts.append("修改 {} 个文档".format(len(applied)))
        if created:
            parts.append("新建 {} 个文档".format(len(created)))
        if not parts:
            parts.append("无改动")
        return prefix + "，".join(parts)
