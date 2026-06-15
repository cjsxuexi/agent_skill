import os
import unittest

import _support  # noqa: F401
from wiki_engine import parser, lint
from wiki_engine.lint.base import LintContext, ERROR
from wiki_engine.doc_kind import DocKind


def _ctx(fixture, kind, rel=None, doc_root=None, source_root=None, text=None):
    if text is None:
        text = _support.read_fixture(fixture)
    rel = rel or fixture
    doc = parser.parse(rel, text)
    return LintContext(rel, doc, kind, doc_root=doc_root, source_root=source_root)


def _ids(findings):
    return [f.rule_id for f in findings]


class LintRuleTest(unittest.TestCase):
    def test_no_section_11plus_strict_fires(self):
        ctx = _ctx("drift_subsystem.md", DocKind.SUBSYSTEM, rel="port-data/architecture.md")
        f = lint.run_lint(ctx)
        hits = [x for x in f if x.rule_id == "STRUCT_NO_SECTION_11PLUS"]
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].blocking, "HARD")

    def test_same_section_11_light_legal(self):
        # the plan §3 约束 4: identical ## 11. is illegal in strict, legal in light
        ctx = _ctx("ancillary.md", DocKind.ANCILLARY, rel="port-device/alarm-architecture.md")
        self.assertNotIn("STRUCT_NO_SECTION_11PLUS", _ids(lint.run_lint(ctx)))

    def test_clean_subsystem_no_11plus_no_title_drift(self):
        ctx = _ctx("clean_subsystem.md", DocKind.SUBSYSTEM, rel="port-device/architecture.md")
        ids = _ids(lint.run_lint(ctx))
        self.assertNotIn("STRUCT_NO_SECTION_11PLUS", ids)
        self.assertNotIn("STRUCT_TITLE_CANONICAL", ids)

    def test_title_canonical_info_on_gailan(self):
        ctx = _ctx("drift_subsystem.md", DocKind.SUBSYSTEM, rel="port-data/architecture.md")
        hits = [x for x in lint.run_lint(ctx) if x.rule_id == "STRUCT_TITLE_CANONICAL"]
        self.assertTrue(hits)
        self.assertEqual(hits[0].severity, "INFO")
        self.assertEqual(hits[0].blocking, "never")

    def test_speculation_pos_neg(self):
        good = "# x\n\n## 6. 业务流\n\n`t_x` 由作业同步写入。\n\n## 10. 待确认 / 疑问\n\n无\n"
        bad = "# x\n\n## 6. 业务流\n\n该 topic 可能由 port-gateway 推送。\n\n## 10. 待确认 / 疑问\n\n无\n"
        self.assertNotIn("SPEC_NO_SPECULATION",
                         _ids(lint.run_lint(_ctx(None, DocKind.SUBSYSTEM, rel="x.md", text=good))))
        self.assertIn("SPEC_NO_SPECULATION",
                      _ids(lint.run_lint(_ctx(None, DocKind.SUBSYSTEM, rel="x.md", text=bad))))

    def test_anchor_lineno_fires(self):
        bad = "# x\n\n## 4. 对外接口\n\n`OrderService#refund (src/Order.java:L28)`\n\n## 10. 待确认 / 疑问\n\n无\n"
        self.assertIn("ANCHOR_NO_LINENO",
                      _ids(lint.run_lint(_ctx(None, DocKind.SUBSYSTEM, rel="x.md", text=bad))))

    def test_derived_file_link_hard(self):
        bad = "# x\n\n## 1. 概述\n\n见 [清单](./.questions.md)。\n"
        hits = [f for f in lint.run_lint(_ctx(None, DocKind.ANCILLARY, rel="x.md", text=bad))
                if f.rule_id == "LINK_DERIVED_FILE"]
        self.assertTrue(hits)
        self.assertEqual(hits[0].blocking, "HARD")

    def test_link_anchor_resolution(self):
        ctx = _ctx("linkset/a.md", DocKind.ANCILLARY, rel="a.md",
                   doc_root=os.path.join(_support.FIXTURES, "linkset"))
        f = lint.run_lint(ctx)
        ids = _ids(f)
        self.assertIn("LINK_ANCHOR_RESOLVES", ids)   # #9-不存在的锚点
        self.assertIn("LINK_DERIVED_FILE", ids)       # ./.questions.md
        # the valid #1-概述 link must NOT produce an anchor finding for b.md
        bad_anchor = [x for x in f if x.rule_id == "LINK_ANCHOR_RESOLVES"]
        self.assertTrue(all("不存在" in x.message_zh for x in bad_anchor))

    def test_data_name_grep_skip_without_source(self):
        ctx = _ctx("drift_subsystem.md", DocKind.SUBSYSTEM, rel="port-data/architecture.md")
        hits = [f for f in lint.run_lint(ctx) if f.rule_id == "DATA_NAME_GREP"]
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].severity, "WARN")
        self.assertIn("跳过", hits[0].message_zh)

    def test_data_name_grep_present_in_source(self):
        ctx = _ctx("drift_subsystem.md", DocKind.SUBSYSTEM, rel="port-data/architecture.md",
                   source_root=os.path.join(_support.FIXTURES, "srcset"))
        errs = [f for f in lint.run_lint(ctx) if f.rule_id == "DATA_NAME_GREP" and f.severity == ERROR]
        self.assertEqual(errs, [])   # dws_vessel_job is greppable in Foo.java

    def test_data_name_grep_missing_in_source(self):
        bad = ("# x\n\n## 7. 数据资产\n\n### 7.1 关系型数据库表\n"
               "| 表名 | 主键 | 读取的入口 | 写入的入口 |\n|---|---|---|---|\n"
               "| `t_missing_table` | id | a | b |\n\n## 10. 待确认 / 疑问\n\n无\n")
        ctx = _ctx(None, DocKind.SUBSYSTEM, rel="x.md", text=bad,
                   source_root=os.path.join(_support.FIXTURES, "srcset"))
        errs = [f for f in lint.run_lint(ctx) if f.rule_id == "DATA_NAME_GREP" and f.severity == ERROR]
        self.assertTrue(errs)

    def test_q10_format_violation(self):
        bad = "# x\n\n## 10. 待确认 / 疑问\n\n- 这条没有定位标签也没有已检查字段。\n"
        self.assertIn("Q10_FORMAT",
                      _ids(lint.run_lint(_ctx(None, DocKind.SINGLE, rel="architecture.md", text=bad))))

    def test_root_numbered_chapter(self):
        ctx = _ctx("root_doc.md", DocKind.ROOT, rel="architecture.md")
        self.assertIn("ROOT_NUMBERED_CHAPTER", _ids(lint.run_lint(ctx)))

    def test_common_frontmatter_valid_and_invalid(self):
        ok = _ctx("_common/coordinate-heading-terms.md", DocKind.COMMON,
                  rel="_common/coordinate-heading-terms.md")
        fm_hits = [f for f in lint.run_lint(ok) if f.rule_id == "COMMON_FRONTMATTER"]
        self.assertEqual(fm_hits, [])
        bad = "---\ncommon_type: other\nlevel: site\n---\n# x\n\n## 1. 范围与级别\n\n无\n\n## 待确认 / 疑问\n\n无\n"
        ctx = _ctx(None, DocKind.COMMON, rel="_common/x.md", text=bad)
        self.assertIn("COMMON_FRONTMATTER", _ids(lint.run_lint(ctx)))


class RuleCatalogTest(unittest.TestCase):
    def test_every_rule_cites_a_contract_clause(self):
        for entry in lint.rule_catalog():
            self.assertTrue(entry["contract"].strip(), entry["rule_id"])

    def test_representative_rules_present(self):
        ids = {e["rule_id"] for e in lint.rule_catalog()}
        for rid in ["STRUCT_NO_SECTION_11PLUS", "ANCHOR_NO_LINENO", "DATA_NAME_GREP",
                    "SPEC_NO_SPECULATION", "STRUCT_TITLE_CANONICAL"]:
            self.assertIn(rid, ids)

    def test_ownership_marked_llm_only(self):
        cat = {e["rule_id"]: e for e in lint.rule_catalog()}
        self.assertTrue(cat["OWNERSHIP_FOREIGN_IDENTIFIER"]["llm_only"])

    def test_blocking_levels_are_valid(self):
        for e in lint.rule_catalog():
            self.assertIn(e["blocking"], ("HARD", "delta", "never"))


if __name__ == "__main__":
    unittest.main()
