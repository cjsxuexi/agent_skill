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


    def test_multi_subsystem_uses_structural_digest(self):
        # real 系统总览 scaffold: H1, blockquote, 子系统清单 table, mermaid, then only
        # the boilerplate 拓扑层级 line — no descriptive prose. 说明 must be the
        # subsystem digest, never the boilerplate or the mermaid body.
        self._repo("multi",
                   "# 系统总览\n\n"
                   "> 由 /document-systems 生成\n> 子系统数量：3\n\n"
                   "## 子系统清单\n\n"
                   "| 子系统 | 类型 | 路径 | 详细文档 |\n|---|---|---|---|\n"
                   "| port-a | Java 服务 | port-a | [→](./port-a/architecture.md) |\n"
                   "| port-b | Java 服务 | port-b | [→](./port-b/architecture.md) |\n"
                   "| port-c | Java 服务 | port-c | [→](./port-c/architecture.md) |\n\n"
                   "## 依赖关系图\n\n```mermaid\ngraph TD\n  port-a --> port-b\n```\n\n"
                   "## 拓扑层级\n\n层级用于决定文档生成顺序，下层依赖上层。\n")
        out = domain_index.build_index(self.tmp, "old_project")
        self.assertIn("3 个子系统：port-a、port-b、port-c", out)
        self.assertNotIn("层级用于决定文档生成顺序", out)   # boilerplate never leaks
        self.assertNotIn("graph TD", out)

    def test_digest_caps_and_appends_ellipsis(self):
        rows = "".join(
            "| port-{0} | Java | port-{0} | [→](x) |\n".format(i) for i in range(8))
        self._repo("big",
                   "# 系统总览\n\n> 子系统数量：8\n\n"
                   "## 子系统清单\n\n| 子系统 | 类型 | 路径 | 文档 |\n|---|---|---|---|\n"
                   + rows + "\n## 依赖关系图\n\n正文。\n")
        out = domain_index.build_index(self.tmp, "old_project")
        self.assertIn("8 个子系统：port-0、port-1、port-2、port-3、port-4、port-5…", out)
        self.assertNotIn("port-6", out)   # capped at 6 names

    def test_authored_preamble_intro_beats_digest(self):
        # a refined multi-subsystem root: authored intro prose sits in the preamble,
        # BEFORE 子系统清单. That intro wins over the structural digest.
        self._repo("refined",
                   "# 系统总览\n\n"
                   "> 由 /document-systems 自动生成\n> 子系统数量：2\n\n"
                   "refined 是面向港口的车辆管理云端服务，统一调度与状态。\n\n"
                   "> 来源：用户提供知识（2026-06-03）\n\n"
                   "## 子系统清单\n\n| 子系统 | 路径 |\n|---|---|\n"
                   "| svc-a | svc-a |\n| svc-b | svc-b |\n")
        out = domain_index.build_index(self.tmp, "old_project")
        self.assertIn("refined 是面向港口的车辆管理云端服务，统一调度与状态。", out)
        self.assertNotIn("2 个子系统", out)   # digest suppressed when authored intro exists

    def test_single_module_prose_skips_fenced_mermaid(self):
        # a single-module root doc (NO 子系统清单) with a mermaid fence before the
        # intro prose: the fence body must not leak as the 说明 (regression guard).
        self._repo("solo",
                   "# solo 架构文档\n\n"
                   "## 1. 概述\n\n```mermaid\ngraph TD\n  x --> y\n```\n\n"
                   "solo 是单模块服务的真实简介。\n")
        out = domain_index.build_index(self.tmp, "old_project")
        self.assertIn("solo 是单模块服务的真实简介。", out)
        self.assertNotIn("graph TD", out)


if __name__ == "__main__":
    unittest.main()
