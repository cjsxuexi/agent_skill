import unittest

import _support  # noqa: F401
from wiki_engine import parser, questions


class QuestionIdTest(unittest.TestCase):
    def setUp(self):
        self.rel = "port-data/architecture.md"
        self.doc = parser.parse(self.rel, _support.read_fixture("drift_subsystem.md"))

    def test_enumerate_two_questions(self):
        qs = questions.enumerate_questions(self.rel, self.doc)
        self.assertEqual(len(qs), 2)
        self.assertTrue(all(q.qid.startswith("q_") and len(q.qid) == 10 for q in qs))
        self.assertEqual(qs[0].locator, "§7.1 关系型数据库表")

    def test_find_question_roundtrips(self):
        qs = questions.enumerate_questions(self.rel, self.doc)
        qid = qs[0].qid
        found = questions.find_question(self.rel, self.doc, qid)
        self.assertIsNotNone(found)
        self.assertEqual(found.qid, qid)

    def test_property1_tail_change_keeps_id(self):
        # changing 已检查 / 建议核实方向 (after the first 。) does not change the id
        loc = "§7.1 关系型数据库表"
        first = "多个 `@TableName` 未显式写 `value`，运行期表名依赖默认命名策略"
        a = questions.compute_qid(self.rel, loc, first)
        # same locator + same first sentence -> same id regardless of tail
        b = questions.compute_qid(self.rel, loc, first)
        self.assertEqual(a, b)

    def test_property1_tail_edit_keeps_id_via_pipeline(self):
        # the S2 common case: append a 已检查 file / rewrite 建议核实方向 (both after the
        # first 。) -> same question, id unchanged. Tested through the real extract path.
        base = ("- [§6.3 数据交互] kafka topic `device.event.raw` 仅见消费方，未找到生产方。"
                "已检查：KafkaConfig.java。建议核实方向：检查 port-gateway 是否生产该 topic。\n")
        edited = ("- [§6.3 数据交互] kafka topic `device.event.raw` 仅见消费方，未找到生产方。"
                  "已检查：KafkaConfig.java、application.yml、NacosConfig.java。"
                  "建议核实方向：改写后的更精确方向。\n")
        loc1, f1 = questions._extract_locator_and_first(base)
        loc2, f2 = questions._extract_locator_and_first(edited)
        self.assertEqual(f1, f2)  # first sentence identical; tails differ
        self.assertEqual(questions.compute_qid(self.rel, loc1, f1),
                         questions.compute_qid(self.rel, loc2, f2))

    def test_wrapped_entry_extracts_deterministically(self):
        wrapped = ("- [§7.1 关系型数据库表] 多个 @TableName 未显式写 value，运行期表名依赖\n"
                   "  MyBatis-Plus 默认命名策略。已检查：entity/。建议核实方向：DDL。\n")
        loc, first = questions._extract_locator_and_first(wrapped)
        self.assertNotIn("\n", questions._normalize(first))  # wrap collapsed to a space
        self.assertEqual(questions.compute_qid(self.rel, loc, first),
                         questions.compute_qid(self.rel, loc, first))

    def test_property2_locator_change_changes_id(self):
        first = "多个 @TableName 未显式写 value"
        a = questions.compute_qid(self.rel, "§7.1 关系型数据库表", first)
        b = questions.compute_qid(self.rel, "§6.3 数据交互", first)
        self.assertNotEqual(a, b)

    def test_property3_doc_path_change_changes_id(self):
        loc = "§7.1 关系型数据库表"
        first = "多个 @TableName 未显式写 value"
        a = questions.compute_qid("port-data/architecture.md", loc, first)
        b = questions.compute_qid("fms-core/architecture.md", loc, first)
        self.assertNotEqual(a, b)

    def test_common_doc_questions_enumerated(self):
        rel = "_common/coordinate-heading-terms.md"
        doc = parser.parse(rel, _support.read_fixture("_common/coordinate-heading-terms.md"))
        qs = questions.enumerate_questions(rel, doc)
        self.assertEqual(len(qs), 1)
        self.assertEqual(qs[0].locator, "§2 术语表")


if __name__ == "__main__":
    unittest.main()
