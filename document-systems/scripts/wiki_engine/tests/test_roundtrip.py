import os
import unittest

import _support  # noqa: F401
from wiki_engine import parser, render
from wiki_engine.model import Edit


def _all_fixtures():
    out = []
    for root, _dirs, files in os.walk(_support.FIXTURES):
        for f in files:
            if f.endswith(".md"):
                out.append(os.path.join(root, f))
    return sorted(out)


class RoundTripTest(unittest.TestCase):
    """The B-gate first door: render(parse(x)) == x byte-for-byte on every fixture."""

    def test_render_equals_source_on_all_fixtures(self):
        for path in _all_fixtures():
            with open(path, "rb") as fh:
                text = fh.read().decode("utf-8")
            doc = parser.parse(path, text)
            self.assertEqual(render.render(doc), text, "round-trip failed: %s" % path)

    def test_sections_tile_document_exactly(self):
        """preamble + every section span concatenated == the whole text (spans correct,
        no gaps, no overlaps)."""
        for path in _all_fixtures():
            with open(path, "rb") as fh:
                text = fh.read().decode("utf-8")
            doc = parser.parse(path, text)
            if not doc.sections:
                continue
            rebuilt = [text[:doc.preamble_end]]
            for s in doc.sections:
                rebuilt.append(text[s.start:s.end])
            self.assertEqual("".join(rebuilt), text, "section tiling failed: %s" % path)

    def test_crlf_line_endings_preserved(self):
        with open(_support.fixture("drift_subsystem.md"), "rb") as fh:
            text = fh.read().decode("utf-8")
        crlf = text.replace("\r\n", "\n").replace("\n", "\r\n")
        doc = parser.parse("crlf.md", crlf)
        self.assertEqual(render.render(doc), crlf)
        self.assertIn("\r\n", render.render(doc))

    def test_surgical_edit_changes_only_target_span(self):
        with open(_support.fixture("drift_subsystem.md"), "rb") as fh:
            text = fh.read().decode("utf-8")
        doc = parser.parse("x.md", text)
        sec10 = doc.section_by_number("10")
        self.assertIsNotNone(sec10)
        # replace the §10 body with a sentinel; everything else must be byte-identical
        doc.edits.append(Edit(sec10.body_start, sec10.end, "SENTINEL\n"))
        out = render.render(doc)
        expected = text[:sec10.body_start] + "SENTINEL\n" + text[sec10.end:]
        self.assertEqual(out, expected)
        self.assertEqual(out[:sec10.body_start], text[:sec10.body_start])   # prefix untouched
        self.assertEqual(out[sec10.body_start + len("SENTINEL\n"):], text[sec10.end:])  # suffix untouched
        self.assertIn("## 10. 待确认 / 疑问", out)   # the §10 heading line is preserved (body only replaced)
        self.assertIn("## 11.", out)                # §11 left intact
        self.assertNotIn("@TableName", out)         # old §10 body gone


if __name__ == "__main__":
    unittest.main()
