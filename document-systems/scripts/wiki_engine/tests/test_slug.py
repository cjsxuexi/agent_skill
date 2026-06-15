import unittest

import _support  # noqa: F401  (sys.path bootstrap)
from wiki_engine.slug import slug, Slugger


class SlugGoldenTest(unittest.TestCase):
    """Golden table. Every row is anchored to a real or contract heading; the wild
    case is taken verbatim from D:\\wiki cross-document links."""

    GOLDEN = [
        # (heading text, expected anchor)
        ("1. 概述", "1-概述"),
        ("1. 概览", "1-概览"),
        ("10. 待确认 / 疑问", "10-待确认--疑问"),
        ("6. 业务流", "6-业务流"),
        ("7. 数据资产", "7-数据资产"),
        # the wild case — `.` and the two `/` drop, flanking spaces survive as `--`
        ("6.6 OTA / 版本 / 文件日志流", "66-ota--版本--文件日志流"),
        # fullwidth colon (U+FF1A) is punctuation -> dropped
        ("11. 附录：代码锚点索引", "11-附录代码锚点索引"),
        # underscore (Pc) is kept; ASCII letters lowered
        ("t_order_refund_log", "t_order_refund_log"),
        ("OTA命令拉取失败问题", "ota命令拉取失败问题"),
        # leading number with dot
        ("6.13 远程驾驶", "613-远程驾驶"),
        # common-doc skeleton headings
        ("1. 范围与级别", "1-范围与级别"),
        ("待确认 / 疑问", "待确认--疑问"),
        ("2. 对外契约与使用方", "2-对外契约与使用方"),
    ]

    def test_golden_table(self):
        for text, expected in self.GOLDEN:
            self.assertEqual(slug(text), expected, "slug(%r)" % text)


class SluggerDedupTest(unittest.TestCase):
    def test_duplicate_headings_get_numeric_suffix(self):
        s = Slugger()
        self.assertEqual(s.slug("数据交互"), "数据交互")
        self.assertEqual(s.slug("数据交互"), "数据交互-1")
        self.assertEqual(s.slug("数据交互"), "数据交互-2")

    def test_dedup_independent_per_base(self):
        s = Slugger()
        self.assertEqual(s.slug("处理流程"), "处理流程")
        self.assertEqual(s.slug("数据交互"), "数据交互")
        self.assertEqual(s.slug("处理流程"), "处理流程-1")

    def test_reset_clears_state(self):
        s = Slugger()
        s.slug("foo")
        s.reset()
        self.assertEqual(s.slug("foo"), "foo")


if __name__ == "__main__":
    unittest.main()
