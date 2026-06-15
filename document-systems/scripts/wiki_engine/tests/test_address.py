import unittest

import _support  # noqa: F401
from wiki_engine import parser, address, render
from wiki_engine.errors import AddressNotFound, AddressAmbiguous, MatchStale, UsageError

_AMBIG = """# x

## 6. 业务流

### 6.1 OTA 上行

a

### 6.2 OTA 下行

b
"""


class AddressTest(unittest.TestCase):
    def setUp(self):
        self.drift = parser.parse("drift.md", _support.read_fixture("drift_subsystem.md"))
        self.clean = parser.parse("clean.md", _support.read_fixture("clean_subsystem.md"))

    def test_append_table_row_into_71(self):
        t = address.resolve(self.drift, {"section": "7", "subsection": "7.1",
                                         "anchor_mode": "append_table_row"})
        edit = address.build_edit(self.drift, t, "append_table_row",
                                  "| `dws_job_circle` | — | 工班报表查询 | 无 |")
        self.drift.edits.append(edit)
        out = render.render(self.drift)
        self.assertIn("| `dws_job_circle` | — | 工班报表查询 | 无 |", out)
        # the new row sits right after the existing data row, before §7.2
        self.assertLess(out.index("dws_job_circle"), out.index("## 8."))
        self.assertGreater(out.index("dws_job_circle"), out.index("dws_vessel_job"))

    def test_append_table_row_wrong_columns(self):
        t = address.resolve(self.drift, {"section": "7", "subsection": "7.1",
                                         "anchor_mode": "append_table_row"})
        with self.assertRaises(UsageError):
            address.build_edit(self.drift, t, "append_table_row", "| a | b |")

    def test_append_into_subsection(self):
        t = address.resolve(self.drift, {"section": "6", "entry": "6.1",
                                         "subsection": "数据交互", "anchor_mode": "append"})
        edit = address.build_edit(self.drift, t, "append", "- Redis（R/W）：`shift:cache` R\n")
        self.drift.edits.append(edit)
        out = render.render(self.drift)
        self.assertIn("- Redis（R/W）：`shift:cache` R", out)
        self.assertLess(out.index("shift:cache"), out.index("## 7."))

    def test_entry_identifier_unique(self):
        t = address.resolve(self.clean, {"section": "6", "entry": "OTA", "anchor_mode": "append"})
        self.assertEqual(t.heading.number, "6.6")

    def test_entry_identifier_ambiguous(self):
        doc = parser.parse("a.md", _AMBIG)
        with self.assertRaises(AddressAmbiguous):
            address.resolve(doc, {"section": "6", "entry": "OTA", "anchor_mode": "append"})
        # numeric form disambiguates
        t = address.resolve(doc, {"section": "6", "entry": "6.1", "anchor_mode": "append"})
        self.assertEqual(t.heading.number, "6.1")

    def test_section_not_found(self):
        with self.assertRaises(AddressNotFound):
            address.resolve(self.drift, {"section": "99", "anchor_mode": "append"})

    def test_replace_stale_match(self):
        t = address.resolve(self.drift, {"section": "1", "anchor_mode": "replace"})
        with self.assertRaises(MatchStale):
            address.build_edit(self.drift, t, "replace", "新内容", replace_match="这段文字不存在于原文")

    def test_replace_match_ok(self):
        t = address.resolve(self.drift, {"section": "1", "anchor_mode": "replace"})
        edit = address.build_edit(self.drift, t, "replace", "新端口 18000。",
                                  replace_match="端口 17004。")
        self.drift.edits.append(edit)
        out = render.render(self.drift)
        self.assertIn("新端口 18000。", out)
        self.assertNotIn("端口 17004。", out)


if __name__ == "__main__":
    unittest.main()
