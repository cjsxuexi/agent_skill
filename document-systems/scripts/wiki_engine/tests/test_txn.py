"""Transaction pipeline tests (plan §6.5).

Every test that writes uses a tempdir copy of the fixtures, so the real fixtures stay
pristine. The transaction is exercised end-to-end (handlers -> apply -> baseline lint ->
HARD rules -> lint delta -> write-or-not).
"""

import os
import shutil
import tempfile
import unittest

import _support  # noqa: F401
from wiki_engine import parser, questions, io_utf8
from wiki_engine.txn import Transaction
from wiki_engine.errors import CouplingMissing, TransactionRejected, RootEdgeDangling


def _qid(path, rel, idx=0):
    text = io_utf8.read_text(path)
    doc = parser.parse(rel, text)
    return questions.enumerate_questions(rel, doc)[idx].qid


def _bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


def _text(path):
    return io_utf8.read_text(path)


class TxnBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.fix = _support.FIXTURES
        self.pl = os.path.join(self.tmp, "payloads")
        os.makedirs(self.pl)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _copy(self, fixture, rel):
        dst = os.path.join(self.tmp, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy(os.path.join(self.fix, fixture), dst)
        return dst

    def _payload(self, name, content):
        with open(os.path.join(self.pl, name), "w", encoding="utf-8") as fh:
            fh.write(content)
        return "payloads/" + name

    def _txn(self, ops, source_root=None):
        return Transaction(doc_root=self.tmp, source_root=source_root,
                           base_dir=self.tmp, ops_json=ops)


class TxnHappyPathTest(TxnBase):
    def test_s1_full_resolve_coupled_with_update_section(self):
        path = self._copy("drift_subsystem.md", "port-data/architecture.md")
        before_bytes = _bytes(path)
        qid = _qid(path, "port-data/architecture.md")
        cf = self._payload("row.md", "| `dws_job_circle` | — | 工班报表查询 | 无 |")
        ops = [
            {"op": "resolve_question", "target": "port-data/architecture.md",
             "mode": "full", "question_id": qid,
             "coupling": {"kind": "body_edit", "ref_op_index": 1}},
            {"op": "update_section", "target": "port-data/architecture.md",
             "at": {"section": "7", "subsection": "7.1", "anchor_mode": "append_table_row"},
             "content_file": cf},
        ]
        result = self._txn(ops).run(dry_run=False)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["applied"], ["port-data/architecture.md"])
        out = _text(path)
        self.assertIn("dws_job_circle", out)
        self.assertNotIn("@TableName", out)
        self.assertNotEqual(before_bytes, out.encode("utf-8"))   # file was written

    def test_existing_anchor_coupling_satisfied(self):
        # resolve full with an existing_anchor proof (conclusion already in the doc)
        path = self._copy("drift_subsystem.md", "port-data/architecture.md")
        qid = _qid(path, "port-data/architecture.md")
        ops = [
            {"op": "resolve_question", "target": "port-data/architecture.md",
             "mode": "full", "question_id": qid,
             "coupling": {"kind": "existing_anchor",
                          "anchor": "port-data/architecture.md#7-数据资产"}},
        ]
        result = self._txn(ops).run(dry_run=False)
        self.assertEqual(result["status"], "ok")
        out = _text(path)
        self.assertNotIn("@TableName", out)


class TxnCouplingTest(TxnBase):
    def test_full_resolve_no_coupling_rejected(self):
        path = self._copy("drift_subsystem.md", "port-data/architecture.md")
        qid = _qid(path, "port-data/architecture.md")
        ops = [{"op": "resolve_question", "target": "port-data/architecture.md",
                "mode": "full", "question_id": qid}]
        with self.assertRaises(CouplingMissing) as cm:
            self._txn(ops).run(dry_run=False)
        self.assertEqual(cm.exception.exit_code, 5)
        self.assertEqual(_text(path).count("@TableName"), 1)

    def test_full_resolve_dangling_ref_rejected(self):
        path = self._copy("drift_subsystem.md", "port-data/architecture.md")
        qid = _qid(path, "port-data/architecture.md")
        # ref_op_index points at an op that does not provide a body edit (add_question
        # is fine, but here it points past the end)
        ops = [{"op": "resolve_question", "target": "port-data/architecture.md",
                "mode": "full", "question_id": qid,
                "coupling": {"kind": "body_edit", "ref_op_index": 5}}]
        with self.assertRaises(CouplingMissing) as cm:
            self._txn(ops).run(dry_run=False)
        self.assertEqual(cm.exception.exit_code, 5)

    def test_existing_anchor_missing_rejected(self):
        path = self._copy("drift_subsystem.md", "port-data/architecture.md")
        qid = _qid(path, "port-data/architecture.md")
        ops = [{"op": "resolve_question", "target": "port-data/architecture.md",
                "mode": "full", "question_id": qid,
                "coupling": {"kind": "existing_anchor",
                             "anchor": "port-data/architecture.md#99-不存在"}}]
        with self.assertRaises(CouplingMissing):
            self._txn(ops).run(dry_run=False)


class TxnLintDeltaTest(TxnBase):
    def test_introduce_section_11_rejected(self):
        # clean_subsystem has no §11; appending one introduces a HARD finding -> reject
        path = self._copy("clean_subsystem.md", "port-device/architecture.md")
        before = _bytes(path)
        # append a §11 chapter at the doc tail via update_section replace on §10
        cf = self._payload("s11.md",
                           "无\n\n## 11. 附录：代码锚点索引\n\n违规章节。\n")
        ops = [{"op": "update_section", "target": "port-device/architecture.md",
                "at": {"section": "10", "anchor_mode": "replace"},
                "content_file": cf}]
        with self.assertRaises(TransactionRejected) as cm:
            self._txn(ops).run(dry_run=False)
        self.assertEqual(cm.exception.exit_code, 3)
        self.assertIn("§11", cm.exception.message_zh)
        self.assertEqual(_bytes(path), before)   # nothing written

    def test_new_derived_file_link_rejected(self):
        path = self._copy("clean_subsystem.md", "port-device/architecture.md")
        before = _bytes(path)
        cf = self._payload("dlink.md",
                           "无\n\n见 [问题清单](./.questions.md)。\n")
        ops = [{"op": "update_section", "target": "port-device/architecture.md",
                "at": {"section": "10", "anchor_mode": "replace"},
                "content_file": cf}]
        with self.assertRaises(TransactionRejected) as cm:
            self._txn(ops).run(dry_run=False)
        self.assertEqual(cm.exception.exit_code, 3)
        self.assertEqual(_bytes(path), before)

    def test_baseline_drift_does_not_block(self):
        # the DRIFT doc already has §11 + 概览; editing §7/§10 without a NEW violation
        # must SUCCEED (baseline drift is tolerated, plan §6.5 step 5).
        path = self._copy("drift_subsystem.md", "port-data/architecture.md")
        qid = _qid(path, "port-data/architecture.md", idx=1)  # the §5.2 entry
        rf = self._payload("res.md",
                           "- [§5.2 下游] 仍需从网关路由反查全部调用方。"
                           "已检查：controller/。建议核实方向：网关路由表。")
        cf = self._payload("row.md", "| `dws_job_circle` | — | 工班报表查询 | 无 |")
        ops = [
            {"op": "resolve_question", "target": "port-data/architecture.md",
             "mode": "partial", "question_id": qid, "residual_file": rf},
            {"op": "update_section", "target": "port-data/architecture.md",
             "at": {"section": "7", "subsection": "7.1", "anchor_mode": "append_table_row"},
             "content_file": cf},
        ]
        result = self._txn(ops).run(dry_run=False)
        self.assertEqual(result["status"], "ok")
        out = _text(path)
        self.assertIn("dws_job_circle", out)
        self.assertIn("仍需从网关路由反查", out)
        # the pre-existing §11 + 概览 are untouched and did not block
        self.assertIn("## 11.", out)
        self.assertIn("## 1. 概览", out)


class TxnAtomicTest(TxnBase):
    def test_multidoc_rollback_when_one_doc_violates(self):
        # doc A is a clean edit; doc B introduces a §11 -> whole txn rejected, NEITHER
        # file modified on disk.
        pa = self._copy("drift_subsystem.md", "port-data/architecture.md")
        pb = self._copy("clean_subsystem.md", "port-device/architecture.md")
        a_before = _bytes(pa)
        b_before = _bytes(pb)
        qid = _qid(pa, "port-data/architecture.md")
        cfa = self._payload("rowa.md", "| `dws_job_circle` | — | 工班报表查询 | 无 |")
        cfb = self._payload("s11.md", "无\n\n## 11. 非法章节\n\n违规。\n")
        ops = [
            {"op": "resolve_question", "target": "port-data/architecture.md",
             "mode": "full", "question_id": qid,
             "coupling": {"kind": "body_edit", "ref_op_index": 1}},
            {"op": "update_section", "target": "port-data/architecture.md",
             "at": {"section": "7", "subsection": "7.1", "anchor_mode": "append_table_row"},
             "content_file": cfa},
            {"op": "update_section", "target": "port-device/architecture.md",
             "at": {"section": "10", "anchor_mode": "replace"},
             "content_file": cfb},
        ]
        with self.assertRaises(TransactionRejected) as cm:
            self._txn(ops).run(dry_run=False)
        self.assertEqual(cm.exception.exit_code, 3)
        self.assertEqual(_bytes(pa), a_before)   # doc A unchanged
        self.assertEqual(_bytes(pb), b_before)   # doc B unchanged

    def test_dry_run_zero_writes(self):
        path = self._copy("drift_subsystem.md", "port-data/architecture.md")
        before = _bytes(path)
        qid = _qid(path, "port-data/architecture.md")
        cf = self._payload("row.md", "| `dws_job_circle` | — | 工班报表查询 | 无 |")
        ops = [
            {"op": "resolve_question", "target": "port-data/architecture.md",
             "mode": "full", "question_id": qid,
             "coupling": {"kind": "body_edit", "ref_op_index": 1}},
            {"op": "update_section", "target": "port-data/architecture.md",
             "at": {"section": "7", "subsection": "7.1", "anchor_mode": "append_table_row"},
             "content_file": cf},
        ]
        result = self._txn(ops).run(dry_run=True)
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["dry_run"])
        self.assertEqual(_bytes(path), before)   # zero writes


class TxnPromoteTest(TxnBase):
    def _promote_ops(self, level):
        tf = self._payload("title.md", "ego_info 外部生产链路")
        bf = self._payload("body.md", "ego_info 由外部 AntennaServer 上报落 Mongo，本仓只读副本。")
        old = "- 关系型数据库表（R/W）：`dws_vessel_job` R"
        mf = self._payload("old.md", old)
        prefix = "../_common" if level == "repo" else "../../_common"
        ref = self._payload("ref.md",
                            "- 见 [ego-info-source § 范围与级别]({}/ego-info-source.md#1-范围与级别)".format(prefix))
        return [{"op": "promote_to_common", "level": level, "type": "shared-lib",
                 "common_name": "ego-info-source", "title_file": tf, "body_file": bf,
                 "sources": [{"target": "port-data/architecture.md",
                              "at": {"section": "6", "entry": "6.1", "subsection": "数据交互",
                                     "anchor_mode": "replace"},
                              "replace_match_file": mf, "reference_text_file": ref}]}]

    def test_promote_repo_scaffolds_and_lint_passes(self):
        path = self._copy("drift_subsystem.md", "port-data/architecture.md")
        ops = self._promote_ops("repo")
        result = self._txn(ops).run(dry_run=False)
        self.assertEqual(result["status"], "ok")
        common = os.path.join(self.tmp, "_common", "ego-info-source.md")
        self.assertTrue(os.path.exists(common))
        cc = _text(common)
        self.assertIn("level: repo", cc)
        self.assertIn("# ego_info 外部生产链路", cc)
        out = _text(path)
        self.assertIn("ego-info-source § 范围与级别", out)
        self.assertNotIn("- 关系型数据库表（R/W）：`dws_vessel_job` R", out)

    def test_promote_global_scaffolds(self):
        path = self._copy("drift_subsystem.md", "port-data/architecture.md")
        ops = self._promote_ops("global")
        result = self._txn(ops).run(dry_run=False)
        self.assertEqual(result["status"], "ok")
        wiki_base = os.path.dirname(os.path.normpath(self.tmp))
        common = os.path.join(wiki_base, "_common", "ego-info-source.md")
        try:
            self.assertTrue(os.path.exists(common))
            self.assertIn("level: global", _text(common))
        finally:
            if os.path.exists(common):
                os.remove(common)
            cdir = os.path.dirname(common)
            if os.path.isdir(cdir) and not os.listdir(cdir):
                os.rmdir(cdir)


class TxnUpdateRootTest(TxnBase):
    def test_subsystem_row_add(self):
        self._copy("root_doc.md", "architecture.md")
        self._copy("clean_subsystem.md", "port-foo/architecture.md")
        ops = [{"op": "update_root", "target": "architecture.md", "kind": "subsystem_row",
                "action": "add", "name": "port-foo",
                "row": {"类型": "Java 服务", "端口": "17099", "路径": "port-foo",
                        "上游依赖": "port-service",
                        "详细文档": "[查看](./port-foo/architecture.md#1-概述)"}}]
        result = self._txn(ops).run(dry_run=False)
        self.assertEqual(result["status"], "ok")
        out = _text(os.path.join(self.tmp, "architecture.md"))
        self.assertIn("| port-foo | Java 服务 | 17099 |", out)

    def test_mermaid_edge_declared_ok(self):
        self._copy("root_doc.md", "architecture.md")
        ops = [{"op": "update_root", "target": "architecture.md", "kind": "mermaid_edge",
                "action": "add", "from": "port-data", "to": "port-device"}]
        result = self._txn(ops).run(dry_run=True)
        self.assertEqual(result["status"], "ok")

    def test_mermaid_edge_dangling_rejected(self):
        self._copy("root_doc.md", "architecture.md")
        ops = [{"op": "update_root", "target": "architecture.md", "kind": "mermaid_edge",
                "action": "add", "from": "port-data", "to": "port-NOPE"}]
        with self.assertRaises(RootEdgeDangling) as cm:
            self._txn(ops).run(dry_run=False)
        self.assertEqual(cm.exception.exit_code, 3)

    def test_common_index_entry_creates_section(self):
        self._copy("root_doc.md", "architecture.md")
        # the new index row links ./_common/ego-info-source.md — create it so the link
        # resolves (otherwise LINK_TARGET_EXISTS would block, correctly)
        self._copy("_common/coordinate-heading-terms.md", "_common/ego-info-source.md")
        ops = [{"op": "update_root", "target": "architecture.md", "kind": "common_index_entry",
                "action": "add", "name": "ego-info-source", "级别": "仓库级",
                "类型": "shared-lib", "说明": "ego 外部链路"}]
        result = self._txn(ops).run(dry_run=False)
        self.assertEqual(result["status"], "ok")
        out = _text(os.path.join(self.tmp, "architecture.md"))
        self.assertIn("## 仓内公共文档", out)
        self.assertIn("[ego-info-source](./_common/ego-info-source.md)", out)
        self.assertLess(out.index("## 仓内公共文档"), out.index("## 辅助资源"))


if __name__ == "__main__":
    unittest.main()
