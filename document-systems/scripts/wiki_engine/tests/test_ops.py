"""Golden before/after for each of the 6 operators (plan §6.7 / §4).

Each test parses a fixture, applies the op's edits, renders, then asserts the changed
region AND that the rest of the document is byte-identical (surgical splice, plan §3 约束 2).
The ops are driven through a small in-memory Transaction stub so payloads come from temp
files exactly as in production.
"""

import os
import shutil
import tempfile
import unittest

import _support  # noqa: F401
from wiki_engine import parser, render, questions, ops
from wiki_engine.model import Edit
from wiki_engine.errors import UsageError, RootEdgeDangling


class _StubTxn:
    """Minimal Transaction surface the op handlers need: baseline_doc, read_payload,
    rel_key, doc_root, install_root."""

    def __init__(self, doc_root, base_dir, install_root=None):
        self.doc_root = doc_root
        self.base_dir = base_dir
        self.install_root = install_root
        self._cache = {}

    def baseline_doc(self, rel):
        if rel not in self._cache:
            path = os.path.join(self.doc_root, rel)
            with open(path, "rb") as fh:
                text = fh.read().decode("utf-8")
            self._cache[rel] = parser.parse(path, text)
        return self._cache[rel]

    def baseline_text(self, rel):
        return self.baseline_doc(rel).text

    def read_payload(self, rel):
        with open(os.path.join(self.base_dir, rel), "rb") as fh:
            return fh.read().decode("utf-8")

    def rel_key(self, rel):
        return rel.replace("\\", "/")


def _apply(res, txn):
    """Apply an OpResult's edits to a single doc and return (rel, before, after)."""
    rel = res.edits[0][0]
    base = txn.baseline_text(rel)
    edits = [e for r, e in res.edits if r == rel]
    return rel, base, render.apply_edits(base, edits)


class OpsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.fix = _support.FIXTURES
        # doc_root with a port-data/architecture.md (drift) + payloads/
        self.pd = os.path.join(self.tmp, "port-data")
        os.makedirs(self.pd)
        shutil.copy(os.path.join(self.fix, "drift_subsystem.md"),
                    os.path.join(self.pd, "architecture.md"))
        self.pl = os.path.join(self.tmp, "payloads")
        os.makedirs(self.pl)
        self.txn = _StubTxn(self.tmp, self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _payload(self, name, content):
        with open(os.path.join(self.pl, name), "w", encoding="utf-8") as fh:
            fh.write(content)
        return "payloads/" + name

    # --- update_section ----------------------------------------------------
    def test_update_section_append_table_row(self):
        cf = self._payload("row.md", "| `dws_job_circle` | — | 工班报表查询 | 无 |")
        op = {"op": "update_section", "target": "port-data/architecture.md",
              "at": {"section": "7", "subsection": "7.1", "anchor_mode": "append_table_row"},
              "content_file": cf}
        res = ops.op_update_section(self.txn, op, 0)
        self.assertTrue(res.provides_body_edit)
        rel, before, after = _apply(res, self.txn)
        self.assertIn("| `dws_job_circle` | — | 工班报表查询 | 无 |", after)
        # the new row sits after the existing data row, before §7.2
        self.assertLess(after.index("dws_job_circle"), after.index("### 7.2"))
        self.assertGreater(after.index("dws_job_circle"), after.index("dws_vessel_job"))
        # everything before the insert point is byte-identical
        idx = res.edits[0][1].start
        self.assertEqual(after[:idx], before[:idx])
        self.assertEqual(after[idx + len(res.edits[0][1].replacement):], before[idx:])

    # --- resolve_question --------------------------------------------------
    def test_resolve_question_full_deletes_entry(self):
        doc = self.txn.baseline_doc("port-data/architecture.md")
        qs = questions.enumerate_questions("port-data/architecture.md", doc)
        qid = qs[0].qid
        op = {"op": "resolve_question", "target": "port-data/architecture.md",
              "mode": "full", "question_id": qid,
              "coupling": {"kind": "body_edit", "ref_op_index": 1}}
        res = ops.op_resolve_question(self.txn, op, 0)
        self.assertTrue(res.deletes_question)
        self.assertEqual(res.coupling["kind"], "body_edit")
        rel, before, after = _apply(res, self.txn)
        self.assertNotIn("@TableName", after)            # entry 1 gone
        self.assertIn("本服务源码只能确认", after)         # entry 2 intact
        self.assertIn("## 11.", after)                   # everything else intact

    def test_resolve_question_partial_replaces_with_residual(self):
        doc = self.txn.baseline_doc("port-data/architecture.md")
        qs = questions.enumerate_questions("port-data/architecture.md", doc)
        qid = qs[0].qid
        rf = self._payload("residual.md",
                           "- [§7.1 关系型数据库表] 仅 `dws_vessel_job` 一表仍待确认 DDL。"
                           "已检查：entity/。建议核实方向：真实数据库 DDL。")
        op = {"op": "resolve_question", "target": "port-data/architecture.md",
              "mode": "partial", "question_id": qid, "residual_file": rf}
        res = ops.op_resolve_question(self.txn, op, 0)
        rel, before, after = _apply(res, self.txn)
        self.assertIn("仅 `dws_vessel_job` 一表仍待确认", after)
        self.assertNotIn("多个 `@TableName` 未显式写", after)
        self.assertIn("本服务源码只能确认", after)  # entry 2 intact

    def test_resolve_question_unknown_qid_not_found(self):
        from wiki_engine.errors import AddressNotFound
        op = {"op": "resolve_question", "target": "port-data/architecture.md",
              "mode": "full", "question_id": "q_deadbeef",
              "coupling": {"kind": "body_edit", "ref_op_index": 1}}
        with self.assertRaises(AddressNotFound):
            ops.op_resolve_question(self.txn, op, 0)

    # --- add_question ------------------------------------------------------
    def test_add_question_appends_valid_entry(self):
        cf = self._payload("q.md",
                           "- [§6.1 数据交互] topic 生产方未定位。已检查：service/。建议核实方向：网关路由。")
        op = {"op": "add_question", "target": "port-data/architecture.md", "content_file": cf}
        res = ops.op_add_question(self.txn, op, 0)
        rel, before, after = _apply(res, self.txn)
        self.assertIn("topic 生产方未定位", after)
        # appended into §10, before §11
        self.assertLess(after.index("topic 生产方未定位"), after.index("## 11."))
        self.assertGreater(after.index("topic 生产方未定位"), after.index("本服务源码只能确认"))

    def test_add_question_rejects_malformed(self):
        cf = self._payload("bad.md", "- 这条没有定位标签也没有已检查字段。")
        op = {"op": "add_question", "target": "port-data/architecture.md", "content_file": cf}
        with self.assertRaises(UsageError):
            ops.op_add_question(self.txn, op, 0)

    def test_add_question_replaces_wu_placeholder(self):
        # a doc whose §10 body is just 无 should have it replaced, not appended after
        shutil.copy(os.path.join(self.fix, "clean_subsystem.md"),
                    os.path.join(self.tmp, "clean.md"))
        cf = self._payload("q2.md",
                           "- [§6.6 数据交互] 命令确认回执缺失。已检查：service/。建议核实方向：消费侧日志。")
        op = {"op": "add_question", "target": "clean.md", "content_file": cf}
        res = ops.op_add_question(self.txn, op, 0)
        rel, before, after = _apply(res, self.txn)
        self.assertIn("命令确认回执缺失", after)
        # the §10 body's lone 无 is gone
        sec10_after = after[after.index("## 10."):]
        self.assertNotIn("无\n", sec10_after.split("命令确认回执缺失")[0].rsplit("疑问", 1)[-1])

    # --- move_with_reference ----------------------------------------------
    def test_move_with_reference_replaces_span(self):
        old = "- 关系型数据库表（R/W）：`dws_vessel_job` R"
        mf = self._payload("old.md", old)
        ref = self._payload("ref.md",
                            "- 见 [port-ingest § 数据资产](../port-ingest/architecture.md#7-数据资产)")
        op = {"op": "move_with_reference",
              "sources": [{"target": "port-data/architecture.md",
                           "at": {"section": "6", "entry": "6.1", "subsection": "数据交互",
                                  "anchor_mode": "replace"},
                           "replace_match_file": mf, "reference_text_file": ref}]}
        res = ops.op_move_with_reference(self.txn, op, 0)
        self.assertTrue(res.provides_body_edit)
        rel, before, after = _apply(res, self.txn)
        self.assertIn("port-ingest § 数据资产", after)
        self.assertNotIn("- 关系型数据库表（R/W）：`dws_vessel_job` R", after)
        # surgical: §7.1 table still keeps its own dws_vessel_job row
        self.assertIn("| `dws_vessel_job` | — | 工班报表查询 | 无 |", after)

    def test_move_with_reference_stale_match(self):
        from wiki_engine.errors import MatchStale
        mf = self._payload("old2.md", "这段原文不存在于文档中")
        ref = self._payload("ref2.md", "- 引用")
        op = {"op": "move_with_reference",
              "sources": [{"target": "port-data/architecture.md",
                           "at": {"section": "6", "entry": "6.1", "subsection": "数据交互",
                                  "anchor_mode": "replace"},
                           "replace_match_file": mf, "reference_text_file": ref}]}
        with self.assertRaises(MatchStale):
            ops.op_move_with_reference(self.txn, op, 0)

    # --- promote_to_common -------------------------------------------------
    def test_promote_to_common_scaffolds_and_rewrites(self):
        tf = self._payload("title.md", "ego_info 外部生产链路")
        bf = self._payload("body.md", "ego_info 由外部 AntennaServer 上报落 Mongo，本仓只读副本。")
        old = "- 关系型数据库表（R/W）：`dws_vessel_job` R"
        mf = self._payload("old.md", old)
        ref = self._payload("ref.md",
                            "- 见 [ego-info-source § 范围与级别](../_common/ego-info-source.md#1-范围与级别)")
        op = {"op": "promote_to_common", "level": "repo", "type": "shared-lib",
              "common_name": "ego-info-source", "title_file": tf, "body_file": bf,
              "sources": [{"target": "port-data/architecture.md",
                           "at": {"section": "6", "entry": "6.1", "subsection": "数据交互",
                                  "anchor_mode": "replace"},
                           "replace_match_file": mf, "reference_text_file": ref}]}
        res = ops.op_promote_to_common(self.txn, op, 0)
        # the new common file
        self.assertEqual(len(res.new_files), 1)
        abspath, rel_display, content = res.new_files[0]
        self.assertTrue(abspath.replace("\\", "/").endswith("_common/ego-info-source.md"))
        self.assertEqual(rel_display, "_common/ego-info-source.md")
        self.assertFalse(content.startswith("<!--"))   # leading comment stripped
        self.assertIn("# ego_info 外部生产链路", content)
        self.assertIn("level: repo", content)
        self.assertIn("ego_info 由外部 AntennaServer", content)
        self.assertIn("## 待确认 / 疑问", content)
        self.assertIn("无", content.rsplit("待确认", 1)[-1])
        # source rewritten
        rel, before, after = _apply(res, self.txn)
        self.assertIn("ego-info-source § 范围与级别", after)
        self.assertNotIn("- 关系型数据库表（R/W）：`dws_vessel_job` R", after)

    def test_promote_to_common_global_path(self):
        tf = self._payload("t.md", "全局术语")
        bf = self._payload("b.md", "| `x` | y | z |")
        op = {"op": "promote_to_common", "level": "global", "type": "glossary",
              "common_name": "global-terms", "title_file": tf, "body_file": bf,
              "sources": []}
        res = ops.op_promote_to_common(self.txn, op, 0)
        abspath, rel_display, content = res.new_files[0]
        # global -> dirname(doc_root)/_common
        wiki_base = os.path.dirname(os.path.normpath(self.tmp))
        self.assertEqual(os.path.normpath(abspath),
                         os.path.normpath(os.path.join(wiki_base, "_common", "global-terms.md")))
        self.assertEqual(rel_display, "../_common/global-terms.md")
        self.assertIn("level: global", content)

    # --- update_root -------------------------------------------------------
    def _root_txn(self):
        shutil.copy(os.path.join(self.fix, "root_doc.md"),
                    os.path.join(self.tmp, "architecture.md"))
        return _StubTxn(self.tmp, self.tmp)

    def test_update_root_subsystem_row(self):
        txn = self._root_txn()
        op = {"op": "update_root", "target": "architecture.md", "kind": "subsystem_row",
              "action": "add", "name": "port-foo",
              "row": {"类型": "Java 服务", "端口": "17099", "路径": "port-foo",
                      "上游依赖": "port-service", "详细文档": "[查看](./port-foo/architecture.md#1-概述)"}}
        res = ops.op_update_root(txn, op, 0)
        rel, before, after = _apply(res, txn)
        self.assertIn("| port-foo | Java 服务 | 17099 | port-foo | port-service |", after)
        # inserted into 子系统清单, before 依赖关系图
        self.assertLess(after.index("17099"), after.index("## 依赖关系图"))
        # frontmatter + 系统架构特点 + illegal §6 untouched (EOL-agnostic: the engine
        # preserves whatever line endings the fixture has on this platform)
        self.assertTrue(after.replace("\r\n", "\n").startswith("---\nwhole_architecture"))
        self.assertIn("## 系统架构特点", after)
        self.assertIn("## 6. port-data 报表数据链路补充", after)

    def test_update_root_mermaid_node_and_edge(self):
        txn = self._root_txn()
        # node
        op = {"op": "update_root", "target": "architecture.md", "kind": "mermaid_node",
              "action": "add", "node_id": "port-foo", "label": "port-foo<br/>:17099"}
        res = ops.op_update_root(txn, op, 0)
        rel, before, after = _apply(res, txn)
        self.assertIn('port-foo["port-foo<br/>:17099"]', after)
        # node inserted inside the fence, before closing ```
        fence_close = after.index("```", after.index("```mermaid") + 3)
        self.assertLess(after.index('port-foo['), fence_close)

    def test_update_root_mermaid_edge_declared_ok(self):
        txn = self._root_txn()
        op = {"op": "update_root", "target": "architecture.md", "kind": "mermaid_edge",
              "action": "add", "from": "port-data", "to": "port-device"}
        res = ops.op_update_root(txn, op, 0)
        rel, before, after = _apply(res, txn)
        self.assertIn("port-data --> port-device", after)

    def test_update_root_mermaid_edge_dangling(self):
        txn = self._root_txn()
        op = {"op": "update_root", "target": "architecture.md", "kind": "mermaid_edge",
              "action": "add", "from": "port-data", "to": "port-NOPE"}
        with self.assertRaises(RootEdgeDangling) as cm:
            ops.op_update_root(txn, op, 0)
        self.assertEqual(cm.exception.exit_code, 3)
        self.assertEqual(cm.exception.code, "E_ROOT_EDGE_DANGLING")

    def test_update_root_common_index_creates_section(self):
        txn = self._root_txn()
        op = {"op": "update_root", "target": "architecture.md", "kind": "common_index_entry",
              "action": "add", "name": "ego-info-source", "级别": "仓库级",
              "类型": "shared-lib", "说明": "ego 外部链路"}
        res = ops.op_update_root(txn, op, 0)
        rel, before, after = _apply(res, txn)
        self.assertIn("## 仓内公共文档", after)
        self.assertIn("[ego-info-source](./_common/ego-info-source.md)", after)
        # created right before 辅助资源
        self.assertLess(after.index("## 仓内公共文档"), after.index("## 辅助资源"))

    def test_update_root_protocol_and_aux(self):
        txn = self._root_txn()
        op = {"op": "update_root", "target": "architecture.md", "kind": "protocol_row",
              "action": "add", "row": ["gRPC", "流式 RPC", "port-foo"]}
        res = ops.op_update_root(txn, op, 0)
        rel, before, after = _apply(res, txn)
        self.assertIn("| gRPC | 流式 RPC | port-foo |", after)

        txn2 = self._root_txn()
        op2 = {"op": "update_root", "target": "architecture.md", "kind": "aux_resource",
               "action": "add", "bullet": "`scripts/` — 运维脚本"}
        res2 = ops.op_update_root(txn2, op2, 0)
        rel2, before2, after2 = _apply(res2, txn2)
        # 辅助资源 body was 无 -> replaced
        aux_block = after2[after2.index("## 辅助资源"):after2.index("## 文档维护说明")]
        self.assertIn("- `scripts/` — 运维脚本", aux_block)
        self.assertNotIn("无", aux_block)


if __name__ == "__main__":
    unittest.main()
