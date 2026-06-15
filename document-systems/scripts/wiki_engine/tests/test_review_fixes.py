"""Tests added from the engine adversarial review: cross-file write atomicity,
overlapping-edit rejection, escaped pipes, first-table consistency, CLI JSON contract."""

import os
import shutil
import json
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import _support  # noqa: F401
from wiki_engine import io_utf8, parser, address, render
from wiki_engine.errors import IOFailure, TransactionRejected
from wiki_engine.txn import Transaction

CLI = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cli.py")


class AtomicWriteTest(unittest.TestCase):
    def test_rollback_on_phase2_failure(self):
        d = tempfile.mkdtemp()
        try:
            a = os.path.join(d, "a.md")
            b = os.path.join(d, "b.md")           # does not exist yet
            io_utf8.write_text(a, "ORIG-A\n")
            real_replace = os.replace
            calls = {"n": 0}

            def flaky(src, dst):
                calls["n"] += 1
                if calls["n"] == 2:               # fail committing the 2nd file
                    raise OSError("simulated commit failure")
                return real_replace(src, dst)

            with mock.patch("wiki_engine.io_utf8.os.replace", side_effect=flaky):
                with self.assertRaises(IOFailure):
                    io_utf8.atomic_write_many([(a, "NEW-A\n"), (b, "NEW-B\n")])
            # doc A restored to original; new file B never left behind
            self.assertEqual(io_utf8.read_text(a), "ORIG-A\n")
            self.assertFalse(os.path.exists(b))
            # no stray temp files
            self.assertEqual([f for f in os.listdir(d) if f.startswith(".wiki_engine.")], [])
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_happy_path_writes_all(self):
        d = tempfile.mkdtemp()
        try:
            a = os.path.join(d, "a.md")
            b = os.path.join(d, "sub", "b.md")
            io_utf8.atomic_write_many([(a, "A\n"), (b, "B\n")])
            self.assertEqual(io_utf8.read_text(a), "A\n")
            self.assertEqual(io_utf8.read_text(b), "B\n")
        finally:
            shutil.rmtree(d, ignore_errors=True)


class TxnOverlapTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.doc_root = os.path.join(self.d, "repo")
        os.makedirs(os.path.join(self.doc_root, "port-data"))
        shutil.copy(_support.fixture("drift_subsystem.md"),
                    os.path.join(self.doc_root, "port-data", "architecture.md"))
        self.base = os.path.join(self.d, "payloads")
        os.makedirs(self.base)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def _payload(self, name, content):
        io_utf8.write_text(os.path.join(self.base, name), content)
        return name

    def test_overlapping_edits_same_doc_rejected(self):
        ops = [
            {"op": "update_section", "target": "port-data/architecture.md",
             "at": {"section": "1", "anchor_mode": "replace"},
             "content_file": self._payload("p1.md", "AAA\n")},
            {"op": "update_section", "target": "port-data/architecture.md",
             "at": {"section": "1", "anchor_mode": "replace"},
             "content_file": self._payload("p2.md", "BBB\n")},
        ]
        txn = Transaction(self.doc_root, None, self.base, ops)
        with self.assertRaises(TransactionRejected) as cm:
            txn.run(dry_run=True)
        self.assertIn("冲突", cm.exception.message_zh)
        # rejected dry-run wrote nothing
        with open(os.path.join(self.doc_root, "port-data", "architecture.md"), "rb") as fh:
            self.assertIn("概览", fh.read().decode("utf-8"))


class ParserAddressFixTest(unittest.TestCase):
    def test_split_row_escaped_pipe(self):
        cells = parser.split_row(r"| a\|b | c |")
        self.assertEqual(cells, [r"a\|b", "c"])

    def test_build_edit_uses_first_table(self):
        # two tables in one node span -> append must hit the FIRST (deterministic)
        text = ("# x\n\n## 9. 多表\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n"
                "| C | D |\n|---|---|\n| 3 | 4 |\n")
        doc = parser.parse("x.md", text)
        t = address.resolve(doc, {"section": "9", "anchor_mode": "append_table_row"})
        edit = address.build_edit(doc, t, "append_table_row", "| 9 | 9 |")
        doc.edits.append(edit)
        out = render.render(doc)
        # appended into the FIRST table (before the second table block)
        self.assertLess(out.index("| 9 | 9 |"), out.index("| C | D |"))


class CliContractTest(unittest.TestCase):
    def _run(self, *args):
        return subprocess.run([sys.executable, "-X", "utf8", CLI, *args],
                              capture_output=True, text=True, encoding="utf-8")

    def test_no_subcommand_emits_json(self):
        r = self._run()
        self.assertEqual(r.returncode, 2)
        self.assertEqual(json.loads(r.stdout)["code"], "E_USAGE")

    def test_bad_args_emits_json(self):
        r = self._run("lint")  # missing required --path
        self.assertEqual(r.returncode, 2)
        self.assertEqual(json.loads(r.stdout)["code"], "E_USAGE")

    def test_unknown_subcommand_emits_json(self):
        r = self._run("frobnicate")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(json.loads(r.stdout)["code"], "E_USAGE")


class QidNamespaceTest(unittest.TestCase):
    """Regression: the qid from `questions --doc-root <root>` must match the namespace
    `apply` uses (the doc rel-to-doc_root target), or resolve_question fails E_ADDR_NOTFOUND."""

    def test_questions_qid_resolves_in_apply(self):
        d = tempfile.mkdtemp()
        try:
            droot = os.path.join(d, "repo")
            os.makedirs(os.path.join(droot, "port-data"))
            shutil.copy(_support.fixture("drift_subsystem.md"),
                        os.path.join(droot, "port-data", "architecture.md"))
            r = subprocess.run(
                [sys.executable, "-X", "utf8", CLI, "questions",
                 "--path", os.path.join(droot, "port-data", "architecture.md"),
                 "--doc-root", droot],
                capture_output=True, text=True, encoding="utf-8")
            qs = json.loads(r.stdout)["questions"]
            self.assertTrue(qs)
            self.assertEqual(qs[0]["doc"], "port-data/architecture.md")
            qid = qs[0]["qid"]

            base = os.path.join(d, "work")
            os.makedirs(base)
            with open(os.path.join(base, "res.md"), "w", encoding="utf-8") as f:
                f.write("- [§7.1 关系型数据库表] 残余：仅确认部分。已检查：entity/。建议核实方向：DDL。\n")
            txn = {"version": 1, "doc_root": droot, "intent": "t", "ops": [
                {"op": "resolve_question", "target": "port-data/architecture.md",
                 "mode": "partial", "question_id": qid, "residual_file": "res.md"}]}
            with open(os.path.join(base, "t.json"), "w", encoding="utf-8") as f:
                json.dump(txn, f, ensure_ascii=False)
            r2 = subprocess.run(
                [sys.executable, "-X", "utf8", CLI, "apply",
                 "--txn", os.path.join(base, "t.json"), "--dry-run"],
                capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(r2.returncode, 0, r2.stdout)
            self.assertEqual(json.loads(r2.stdout)["status"], "ok")
        finally:
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
