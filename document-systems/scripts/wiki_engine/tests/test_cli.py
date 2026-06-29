"""CLI subprocess tests (plan §6.2, §6.8).

Runs cli.py via ``sys.executable -X utf8`` so the real argparse / JSON / exit-code path
is exercised exactly as the skills invoke it. Tests that write use a tempdir copy of the
fixtures so the real fixtures stay pristine.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import _support  # noqa: F401

_CLI = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cli.py")


def _run(*args):
    proc = subprocess.run(
        [sys.executable, "-X", "utf8", _CLI, *args],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    out = proc.stdout.decode("utf-8")
    return proc.returncode, out


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.fix = _support.FIXTURES

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _copy(self, fixture, rel):
        dst = os.path.join(self.tmp, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy(os.path.join(self.fix, fixture), dst)
        return dst

    def test_rule_catalog(self):
        code, out = _run("rule-catalog")
        self.assertEqual(code, 0)
        data = json.loads(out)
        ids = {r["rule_id"] for r in data["rules"]}
        self.assertIn("STRUCT_NO_SECTION_11PLUS", ids)

    def test_outline(self):
        code, out = _run("outline", "--path",
                         os.path.join(self.fix, "drift_subsystem.md"))
        self.assertEqual(code, 0)
        data = json.loads(out)
        nums = [s["number"] for s in data["sections"]]
        self.assertIn("1", nums)
        self.assertIn("11", nums)

    def test_lint_exit0_with_findings(self):
        # the drift doc has findings, but lint exits 0 (findings are the product)
        path = self._copy("drift_subsystem.md", "port-data/architecture.md")
        code, out = _run("lint", "--path", os.path.dirname(os.path.dirname(path)),
                         "--recursive")
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertTrue(data["count"] > 0)
        self.assertTrue(data["has_error"])

    def test_lint_strict_exit3_on_error(self):
        path = self._copy("drift_subsystem.md", "port-data/architecture.md")
        code, out = _run("lint", "--path", os.path.dirname(os.path.dirname(path)),
                         "--recursive", "--strict")
        self.assertEqual(code, 3)
        json.loads(out)  # still valid JSON

    def test_lint_strict_clean_exit0(self):
        # a doc with no ERROR findings under --strict exits 0
        self._copy("clean_subsystem.md", "architecture.md")
        code, out = _run("lint", "--path", os.path.join(self.tmp, "architecture.md"),
                         "--strict")
        data = json.loads(out)
        # clean_subsystem has no ERROR findings (only WARN/INFO) -> exit 0
        self.assertEqual(code, 0 if not data["has_error"] else 3)

    def test_questions_recursive(self):
        self._copy("drift_subsystem.md", "port-data/architecture.md")
        code, out = _run("questions", "--path", self.tmp, "--recursive")
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(len(data["questions"]), 2)
        self.assertTrue(all(q["qid"].startswith("q_") for q in data["questions"]))

    def test_apply_dry_run_zero_writes(self):
        path = self._copy("drift_subsystem.md", "port-data/architecture.md")
        with open(path, "rb") as fh:
            before = fh.read()
        # baseline qid
        from wiki_engine import parser, questions, io_utf8
        doc = parser.parse("port-data/architecture.md", io_utf8.read_text(path))
        qid = questions.enumerate_questions("port-data/architecture.md", doc)[0].qid
        # payloads + txn json under tmp
        pl = os.path.join(self.tmp, "payloads")
        os.makedirs(pl)
        with open(os.path.join(pl, "row.md"), "w", encoding="utf-8") as fh:
            fh.write("| `dws_job_circle` | — | 工班报表查询 | 无 |")
        txn = {
            "version": 1, "doc_root": self.tmp,
            "intent": "S1 dry-run smoke",
            "ops": [
                {"op": "resolve_question", "target": "port-data/architecture.md",
                 "mode": "full", "question_id": qid,
                 "coupling": {"kind": "body_edit", "ref_op_index": 1}},
                {"op": "update_section", "target": "port-data/architecture.md",
                 "at": {"section": "7", "subsection": "7.1",
                        "anchor_mode": "append_table_row"},
                 "content_file": "payloads/row.md"},
            ],
        }
        txn_path = os.path.join(self.tmp, "txn.json")
        with open(txn_path, "w", encoding="utf-8") as fh:
            json.dump(txn, fh, ensure_ascii=False)
        code, out = _run("apply", "--txn", txn_path, "--dry-run")
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["status"], "ok")
        self.assertTrue(data["dry_run"])
        with open(path, "rb") as fh:
            self.assertEqual(fh.read(), before)   # zero writes


    def test_resolve_domain_no_registry(self):
        wiki = os.path.join(self.tmp, "wiki"); os.makedirs(wiki)
        repo = os.path.join(self.tmp, "code", "old_project", "fabusurfer")
        code, out = _run("resolve-domain", "--repo", repo, "--wiki", wiki)
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["status"], "no_registry")
        self.assertEqual(data["candidate"], "old_project")

    def test_resolve_domain_unknown_exit10(self):
        wiki = os.path.join(self.tmp, "wiki"); os.makedirs(wiki)
        with open(os.path.join(wiki, ".wiki.json"), "w", encoding="utf-8") as fh:
            json.dump({"domains": ["old_project"], "repos": {}}, fh)
        repo = os.path.join(self.tmp, "code", "experiments", "foo")
        code, out = _run("resolve-domain", "--repo", repo, "--wiki", wiki)
        self.assertEqual(code, 10)
        data = json.loads(out)
        self.assertEqual(data["code"], "E_UNKNOWN_DOMAIN")
        self.assertEqual(data["detail"]["candidate"], "experiments")

    def test_resolve_domain_set_persists(self):
        wiki = os.path.join(self.tmp, "wiki"); os.makedirs(wiki)
        repo = os.path.join(self.tmp, "code", "x", "fms-server")
        code, out = _run("resolve-domain", "--repo", repo, "--wiki", wiki, "--set", "fms")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["domain"], "fms")
        with open(os.path.join(wiki, ".wiki.json"), encoding="utf-8") as fh:
            reg = json.load(fh)
        self.assertIn("fms", reg["domains"])      # --set 只登记域白名单
        self.assertNotIn("repos", reg)            # 不再写 repo→域映射

    def test_init_common_domain(self):
        wiki = os.path.join(self.tmp, "wiki")
        os.makedirs(os.path.join(wiki, "old_project", "fabusurfer"))
        code, out = _run("init-common", "--level", "domain", "--type", "glossary",
                         "--name", "shared-terms", "--wiki-base", wiki, "--domain", "old_project")
        self.assertEqual(code, 0)
        data = json.loads(out)
        created = data["created"].replace("\\", "/")
        self.assertTrue(created.endswith("old_project/_common/shared-terms.md"), created)
        with open(data["created"], encoding="utf-8") as fh:
            self.assertIn("level: domain", fh.read())

    def test_init_common_global_under_wiki_base(self):
        wiki = os.path.join(self.tmp, "wiki")
        os.makedirs(wiki)
        code, out = _run("init-common", "--level", "global", "--type", "glossary",
                         "--name", "company-terms", "--wiki-base", wiki)
        self.assertEqual(code, 0)
        data = json.loads(out)
        created = os.path.normpath(data["created"])
        self.assertEqual(created, os.path.normpath(os.path.join(wiki, "_common", "company-terms.md")))
        with open(data["created"], encoding="utf-8") as fh:
            self.assertIn("level: global", fh.read())

    def test_init_common_domain_missing_domain_dir_errors(self):
        wiki = os.path.join(self.tmp, "wiki")
        os.makedirs(wiki)  # wiki 存在，但 wiki/ghost 域目录不存在
        code, out = _run("init-common", "--level", "domain", "--type", "glossary",
                         "--name", "x", "--wiki-base", wiki, "--domain", "ghost")
        self.assertEqual(code, 2)
        data = json.loads(out)
        self.assertEqual(data["code"], "E_USAGE")

    def test_update_domain_index(self):
        wiki = os.path.join(self.tmp, "wiki")
        repo = os.path.join(wiki, "old_project", "fabusurfer")
        os.makedirs(repo)
        with open(os.path.join(repo, "architecture.md"), "w", encoding="utf-8") as fh:
            fh.write("# fabusurfer\n\n云控核心。\n")
        code, out = _run("update-domain-index", "--wiki", wiki, "--domain", "old_project")
        self.assertEqual(code, 0)
        data = json.loads(out)
        idx = data["index"].replace("\\", "/")
        self.assertTrue(idx.endswith("old_project/index.md"), idx)
        with open(data["index"], encoding="utf-8") as fh:
            content = fh.read()
        self.assertIn("[fabusurfer](./fabusurfer/architecture.md)", content)


if __name__ == "__main__":
    unittest.main()
