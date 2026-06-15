import os
import unittest

import _support  # noqa: F401
from wiki_engine import refs


class RefsTest(unittest.TestCase):
    def setUp(self):
        self.linkset = os.path.join(_support.FIXTURES, "linkset")

    def test_compute_refs_finds_referrer(self):
        target = os.path.join(self.linkset, "b.md")
        found = refs.compute_refs(target, self.linkset)
        referrers = {r["referrer"] for r in found}
        self.assertIn("a.md", referrers)

    def test_compute_refs_anchor_filter(self):
        target = os.path.join(self.linkset, "b.md")
        valid = refs.compute_refs(target, self.linkset, anchor="1-概述")
        self.assertTrue(any(r["referrer"] == "a.md" for r in valid))
        none = refs.compute_refs(target, self.linkset, anchor="no-such-anchor")
        self.assertEqual(none, [])

    def test_no_index_file_written(self):
        # refs is computed live; calling it must not create any file
        before = set(os.listdir(self.linkset))
        refs.compute_refs(os.path.join(self.linkset, "b.md"), self.linkset)
        after = set(os.listdir(self.linkset))
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
