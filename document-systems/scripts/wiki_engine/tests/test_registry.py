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
        registry.save_registry(self.wiki,
                               {"domains": ["old_project"], "repos": {"a": "old_project"}})
        reg = registry.load_registry(self.wiki)
        self.assertEqual(reg["domains"], ["old_project"])
        self.assertEqual(reg["repos"], {"a": "old_project"})

    def test_load_fills_missing_keys(self):
        with open(os.path.join(self.wiki, ".wiki.json"), "w", encoding="utf-8") as fh:
            fh.write("{}")
        reg = registry.load_registry(self.wiki)
        self.assertEqual(reg["domains"], [])
        self.assertEqual(reg["repos"], {})

    def test_path_math(self):
        self.assertEqual(registry.repo_name(self._repo("old_project", "fabusurfer")),
                         "fabusurfer")
        self.assertEqual(registry.parent_candidate(self._repo("old_project", "fabusurfer")),
                         "old_project")


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

    def test_repos_hit(self):
        self._write({"domains": ["fms"], "repos": {"fabusurfer": "old_project"}})
        res = registry.resolve(self.wiki, self._repo("anything", "fabusurfer"))
        self.assertEqual(res, {"status": "resolved", "repo": "fabusurfer",
                               "domain": "old_project", "source": "repos"})

    def test_parent_resolves_and_persists(self):
        self._write({"domains": ["old_project"], "repos": {}})
        res = registry.resolve(self.wiki, self._repo("old_project", "fabusurfer"))
        self.assertEqual(res["domain"], "old_project")
        self.assertEqual(res["source"], "parent")
        self.assertEqual(registry.load_registry(self.wiki)["repos"]["fabusurfer"],
                         "old_project")  # 写回

    def test_unknown_raises_with_detail(self):
        self._write({"domains": ["old_project"], "repos": {}})
        with self.assertRaises(UnknownDomain) as cm:
            registry.resolve(self.wiki, self._repo("experiments", "foo"))
        self.assertEqual(cm.exception.detail["candidate"], "experiments")
        self.assertEqual(cm.exception.detail["domains"], ["old_project"])

    def test_set_creates_registry_and_appends_domain(self):
        res = registry.resolve(self.wiki, self._repo("x", "newrepo"), set_domain="newdom")
        self.assertEqual(res["domain"], "newdom")
        reg = registry.load_registry(self.wiki)
        self.assertIn("newdom", reg["domains"])
        self.assertEqual(reg["repos"]["newrepo"], "newdom")


if __name__ == "__main__":
    unittest.main()
