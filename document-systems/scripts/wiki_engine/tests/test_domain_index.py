"""Domain index generator unit tests (域分层设计 §5.4)."""
import os
import shutil
import tempfile
import unittest

import _support  # noqa: F401
from wiki_engine import domain_index


class DomainIndexTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.dom = os.path.join(self.tmp, "old_project")
        self._repo("fabusurfer", "# fabusurfer 系统总览\n\nfabusurfer 是港口云控核心。\n")
        self._repo("common-lib", "# common-lib\n\n共享库与 grpc-api 契约。\n")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _repo(self, name, arch_text):
        d = os.path.join(self.dom, name)
        os.makedirs(d)
        with open(os.path.join(d, "architecture.md"), "w", encoding="utf-8") as fh:
            fh.write(arch_text)

    def test_build_index_lists_repos(self):
        out = domain_index.build_index(self.tmp, "old_project")
        self.assertIn("# old_project 域索引", out)
        self.assertIn("[fabusurfer 系统总览](./fabusurfer/architecture.md)", out)
        self.assertIn("fabusurfer 是港口云控核心。", out)
        self.assertIn("[common-lib](./common-lib/architecture.md)", out)
        self.assertIn("共享库与 grpc-api 契约。", out)
        self.assertIn("./_common/", out)

    def test_build_index_skips_non_repos(self):
        os.makedirs(os.path.join(self.dom, "_common"))          # 下划线命名空间
        os.makedirs(os.path.join(self.dom, "notarepo"))         # 无 architecture.md
        out = domain_index.build_index(self.tmp, "old_project")
        self.assertNotIn("notarepo", out)
        self.assertNotIn("](./_common/architecture.md)", out)

    def test_summary_falls_back_to_repo_name(self):
        self._repo("nohead", "没有一级标题，直接正文一句。\n")
        out = domain_index.build_index(self.tmp, "old_project")
        # 无 H1 时标题回退为仓名，链接文本即仓名
        self.assertIn("[nohead](./nohead/architecture.md)", out)
        self.assertIn("没有一级标题，直接正文一句。", out)

    def test_pipe_escaped_in_cells(self):
        self._repo("pipey", "# A|B 标题\n\n含 | 竖线 的摘要。\n")
        out = domain_index.build_index(self.tmp, "old_project")
        self.assertIn("A\\|B 标题", out)
        self.assertIn("含 \\| 竖线 的摘要。", out)

    def test_write_index_creates_file(self):
        path = domain_index.write_index(self.tmp, "old_project")
        self.assertEqual(os.path.normpath(path),
                         os.path.normpath(os.path.join(self.dom, "index.md")))
        with open(path, encoding="utf-8") as fh:
            self.assertIn("old_project 域索引", fh.read())

    def test_summary_skips_frontmatter(self):
        self._repo("withfm",
                   "---\ntitle: x\nstatus: draft\n---\n# withfm 标题\n\nwithfm 的摘要句。\n")
        out = domain_index.build_index(self.tmp, "old_project")
        self.assertIn("[withfm 标题](./withfm/architecture.md)", out)
        self.assertIn("withfm 的摘要句。", out)
        self.assertNotIn("title: x", out)  # frontmatter 不当摘要


if __name__ == "__main__":
    unittest.main()
