import unittest

import _support  # noqa: F401
from wiki_engine import parser


class ParserStructureTest(unittest.TestCase):
    def setUp(self):
        self.drift = parser.parse("drift.md", _support.read_fixture("drift_subsystem.md"))
        self.clean = parser.parse("clean.md", _support.read_fixture("clean_subsystem.md"))
        self.root = parser.parse("root.md", _support.read_fixture("root_doc.md"))

    def test_top_level_sections_numbered(self):
        nums = [s.number for s in self.drift.sections]
        for n in ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11"]:
            self.assertIn(n, nums)

    def test_drift_title_is_gailan(self):
        s1 = self.drift.section_by_number("1")
        self.assertEqual(s1.title, "概览")  # the real drift: 概览 not 概述
        self.assertEqual(s1.anchor, "1-概览")

    def test_section6_entries_and_subsections(self):
        s6 = self.drift.section_by_number("6")
        child_numbers = [c.number for c in s6.children]
        self.assertIn("6.1", child_numbers)
        child_titles = [c.title for c in s6.children]
        self.assertIn("处理流程", child_titles)
        self.assertIn("数据交互", child_titles)

    def test_wild_anchor_on_clean_subsystem(self):
        s6 = self.clean.section_by_number("6")
        ota = [c for c in s6.children if c.number == "6.6"]
        self.assertTrue(ota)
        self.assertEqual(ota[0].anchor, "66-ota--版本--文件日志流")

    def test_section7_table_columns(self):
        s7 = self.drift.section_by_number("7")
        # 7.1 sub-table lives inside §7
        sub71 = [c for c in s7.children if c.number == "7.1"][0]
        # span of 7.1 block = from its heading to next child or section end
        idx = s7.children.index(sub71)
        block_end = s7.children[idx + 1].line_start if idx + 1 < len(s7.children) else s7.end
        tables = parser.tables_in(self.drift.text, sub71.line_start, block_end)
        self.assertEqual(len(tables), 1)
        self.assertEqual(tables[0].ncols, 4)
        self.assertEqual(tables[0].header_cells, ["表名", "主键 / 关键索引", "读取的入口", "写入的入口"])
        self.assertEqual(tables[0].row_count, 1)

    def test_links_parsed_with_anchors(self):
        targets = {(l.target, l.anchor) for l in self.drift.links}
        self.assertIn(("../port-service/architecture.md", "4-对外接口"), targets)
        self.assertIn(("./lineage-open-questions.md", None), targets)

    def test_root_frontmatter_yaml(self):
        self.assertEqual(self.root.frontmatter.kind, "yaml")
        self.assertEqual(self.root.frontmatter.data.get("whole_architecture"), "./whole_architecture.md")

    def test_root_has_named_and_drift_sections(self):
        titles = [s.title for s in self.root.sections]
        self.assertIn("子系统清单", titles)
        self.assertIn("依赖关系图", titles)
        self.assertIn("系统架构特点", titles)        # benign drift chapter
        self.assertIsNotNone(self.root.section_by_number("6"))  # illegal numbered drift chapter

    def test_section10_list_items(self):
        s10 = self.drift.section_by_number("10")
        items = parser.list_items_in(self.drift.text, s10.body_start, s10.end)
        self.assertEqual(len(items), 2)
        self.assertIn("@TableName", items[0][2])

    def test_no_frontmatter_on_subsystem(self):
        self.assertEqual(self.drift.frontmatter.kind, "none")


if __name__ == "__main__":
    unittest.main()
