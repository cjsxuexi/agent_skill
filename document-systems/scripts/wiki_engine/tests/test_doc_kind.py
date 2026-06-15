import unittest

import _support  # noqa: F401
from wiki_engine import doc_kind
from wiki_engine.doc_kind import DocKind


class DocKindTest(unittest.TestCase):
    def setUp(self):
        self.root_text = _support.read_fixture("root_doc.md")
        self.single_text = _support.read_fixture("single_mode.md")

    def test_root_vs_single_by_content(self):
        self.assertEqual(doc_kind.classify("architecture.md", self.root_text), DocKind.ROOT)
        self.assertEqual(doc_kind.classify("architecture.md", self.single_text), DocKind.SINGLE)

    def test_subsystem(self):
        self.assertEqual(doc_kind.classify("port-data/architecture.md"), DocKind.SUBSYSTEM)

    def test_ancillary(self):
        self.assertEqual(doc_kind.classify("port-device/alarm-architecture.md"), DocKind.ANCILLARY)
        self.assertEqual(doc_kind.classify("port-data/business-report.md"), DocKind.ANCILLARY)

    def test_common(self):
        self.assertEqual(doc_kind.classify("_common/coordinate-heading-terms.md"), DocKind.COMMON)

    def test_ignored_namespace_and_globs(self):
        cases = [
            "_meta/gitnexus-功能说明.md",
            "issue/OTA命令拉取失败问题.md",
            "whole_architecture.md",
            "spec/external-kafka-upload-20260521/x.md",
            ".review.md",
            "port-data/.review.md",
            ".git/config",
        ]
        for p in cases:
            self.assertEqual(doc_kind.classify(p), DocKind.IGNORED, p)

    def test_strict_light_membership(self):
        # the "same ## 11. , strict illegal / light legal" basis (plan §3 约束 4)
        self.assertIn(doc_kind.classify("port-data/architecture.md"), doc_kind.STRICT)
        self.assertIn(doc_kind.classify("port-device/alarm-architecture.md"), doc_kind.LIGHT)
        self.assertIn(doc_kind.classify("architecture.md", self.single_text), doc_kind.STRICT)
        self.assertIn(doc_kind.classify("_common/x.md"), doc_kind.LIGHT)

    def test_load_ignore_globs_from_contract(self):
        import os
        conv = os.path.join(
            os.path.dirname(_support.FIXTURES), "..", "..", "references", "common-conventions.md"
        )
        conv = os.path.abspath(conv)
        globs = doc_kind.load_ignore_globs(conv)
        self.assertIn("issue/**", globs)
        self.assertIn("**/.review.md", globs)
        self.assertIn("whole_architecture.md", globs)
        self.assertIn("spec/**", globs)


if __name__ == "__main__":
    unittest.main()
