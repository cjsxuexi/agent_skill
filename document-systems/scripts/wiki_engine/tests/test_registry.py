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


if __name__ == "__main__":
    unittest.main()
