"""Domain registry unit tests (域分层设计 §5.2)."""
import json
import os
import shutil
import tempfile
import unittest

import _support  # noqa: F401  (puts scripts/ on sys.path)
from wiki_engine import errors


class ErrorsTest(unittest.TestCase):
    def test_unknown_domain_shape(self):
        self.assertEqual(errors.EXIT_NEED_DOMAIN, 10)
        e = errors.UnknownDomain("父目录不在白名单", detail={"candidate": "experiments"})
        self.assertEqual(e.code, "E_UNKNOWN_DOMAIN")
        self.assertEqual(e.exit_code, 10)
        self.assertEqual(e.to_dict()["detail"]["candidate"], "experiments")


from wiki_engine import registry


class RegistryIOTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.wiki = os.path.join(self.tmp, "wiki")
        os.makedirs(self.wiki)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _repo(self, *parts):
        # 合成的源码仓路径；只用到它的 basename/dirname
        return os.path.join(self.tmp, "code", *parts)

    def test_load_absent_returns_none(self):
        self.assertIsNone(registry.load_registry(self.wiki))

    def test_save_then_load_roundtrip(self):
        registry.save_registry(self.wiki, {"domains": ["old_project"]})
        reg = registry.load_registry(self.wiki)
        self.assertEqual(reg["domains"], ["old_project"])

    def test_load_fills_missing_keys(self):
        with open(os.path.join(self.wiki, ".wiki.json"), "w", encoding="utf-8") as fh:
            fh.write("{}")
        reg = registry.load_registry(self.wiki)
        self.assertEqual(reg["domains"], [])
        self.assertNotIn("repos", reg)

    def test_load_drops_legacy_repos_map(self):
        # 旧式 basename 映射在 load 时被丢弃，下一次 save 即写出干净的 {domains}
        with open(os.path.join(self.wiki, ".wiki.json"), "w", encoding="utf-8") as fh:
            json.dump({"domains": ["old_project"], "repos": {"fms-server": "PSA_FMS"}}, fh)
        reg = registry.load_registry(self.wiki)
        self.assertEqual(reg["domains"], ["old_project"])
        self.assertNotIn("repos", reg)

    def test_path_math(self):
        self.assertEqual(registry.repo_name(self._repo("old_project", "fabusurfer")),
                         "fabusurfer")
        self.assertEqual(registry.parent_candidate(self._repo("old_project", "fabusurfer")),
                         "old_project")

    def test_load_malformed_json_raises_parse_error(self):
        from wiki_engine.errors import ParseError
        with open(os.path.join(self.wiki, ".wiki.json"), "w", encoding="utf-8") as fh:
            fh.write("{ this is not json ")
        with self.assertRaises(ParseError) as cm:
            registry.load_registry(self.wiki)
        self.assertEqual(cm.exception.exit_code, 7)
        self.assertEqual(cm.exception.code, "E_PARSE")


from wiki_engine.errors import UnknownDomain


class ResolveTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.wiki = os.path.join(self.tmp, "wiki")
        os.makedirs(self.wiki)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _repo(self, *parts):
        return os.path.join(self.tmp, "code", *parts)

    def _write(self, data):
        with open(os.path.join(self.wiki, ".wiki.json"), "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)

    def test_no_registry(self):
        res = registry.resolve(self.wiki, self._repo("old_project", "fabusurfer"))
        self.assertEqual(res["status"], "no_registry")
        self.assertEqual(res["candidate"], "old_project")

    def test_parent_resolves_without_persisting(self):
        # 解析 = 父目录名；纯函数，不回写任何 repo→域映射
        self._write({"domains": ["old_project"]})
        res = registry.resolve(self.wiki, self._repo("old_project", "fabusurfer"))
        self.assertEqual(res["domain"], "old_project")
        self.assertEqual(res["source"], "parent")
        self.assertNotIn("repos", registry.load_registry(self.wiki))

    def test_same_basename_different_parent_resolve_to_different_domains(self):
        # 本 issue 的核心：同名仓在不同域文件夹下解析到各自的域，绝不撞键
        self._write({"domains": ["PSA_FMS", "NP_FMS"]})
        psa = registry.resolve(self.wiki, self._repo("PSA_FMS", "fms-server"))
        npr = registry.resolve(self.wiki, self._repo("NP_FMS", "fms-server"))
        self.assertEqual(psa["domain"], "PSA_FMS")
        self.assertEqual(npr["domain"], "NP_FMS")

    def test_set_does_not_cross_overwrite_same_basename(self):
        # 对一个仓 --set 不影响另一个同名仓的解析（DoD #1）
        registry.resolve(self.wiki, self._repo("PSA_FMS", "fms-server"), set_domain="PSA_FMS")
        registry.resolve(self.wiki, self._repo("NP_FMS", "fms-server"), set_domain="NP_FMS")
        psa = registry.resolve(self.wiki, self._repo("PSA_FMS", "fms-server"))
        npr = registry.resolve(self.wiki, self._repo("NP_FMS", "fms-server"))
        self.assertEqual(psa["domain"], "PSA_FMS")
        self.assertEqual(npr["domain"], "NP_FMS")

    def test_unknown_raises_with_detail(self):
        self._write({"domains": ["old_project"]})
        with self.assertRaises(UnknownDomain) as cm:
            registry.resolve(self.wiki, self._repo("experiments", "foo"))
        self.assertEqual(cm.exception.detail["candidate"], "experiments")
        self.assertEqual(cm.exception.detail["domains"], ["old_project"])
        self.assertEqual(cm.exception.detail["repo"], "foo")

    def test_set_creates_registry_and_appends_domain(self):
        res = registry.resolve(self.wiki, self._repo("x", "newrepo"), set_domain="newdom")
        self.assertEqual(res["domain"], "newdom")
        reg = registry.load_registry(self.wiki)
        self.assertIn("newdom", reg["domains"])
        self.assertNotIn("repos", reg)


if __name__ == "__main__":
    unittest.main()
