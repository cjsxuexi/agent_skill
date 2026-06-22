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


if __name__ == "__main__":
    unittest.main()
