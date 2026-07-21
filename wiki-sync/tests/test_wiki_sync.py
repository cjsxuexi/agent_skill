import argparse
import contextlib
import importlib.util
import io
import json
import pathlib
import tempfile
import unittest
from unittest import mock


SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "wiki_sync.py"
SPEC = importlib.util.spec_from_file_location("wiki_sync", SCRIPT)
wiki_sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(wiki_sync)


class CarryOverStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.config = self.root / "config.json"
        self.state = self.root / "state.json"
        self.changeset = self.root / "changeset.json"
        self._write_json(self.config, {
            "repos": [{
                "domain": "domain",
                "repo": "repo",
                "branch": "release",
                "last_synced_sha": "a" * 40,
            }]
        })

    @staticmethod
    def _write_json(path, value):
        path.write_text(json.dumps(value), encoding="utf-8")

    @staticmethod
    def _run(fn, args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            fn(args)
        return json.loads(output.getvalue())

    def test_carry_over_persists_and_advance_clears(self):
        self._write_json(self.state, {
            "from_sha": "a" * 40,
            "to_sha": "b" * 40,
            "reason": "manual_pause",
            "remaining_subsystems": ["one", "two", "one"],
            "detail": "manual carry-over",
        })

        result = self._run(wiki_sync.cmd_carry_over, argparse.Namespace(
            config=str(self.config), repo="domain/repo", state=str(self.state)))

        persisted = json.loads(self.config.read_text(encoding="utf-8"))["repos"][0]
        self.assertEqual(["one", "two"], persisted["carried_over"]["remaining_subsystems"])
        self.assertEqual("manual_pause", result["carried_over"]["reason"])

        advance = self._run(wiki_sync.cmd_advance, argparse.Namespace(
            config=str(self.config), repo="domain/repo", sha="b" * 40))
        persisted = json.loads(self.config.read_text(encoding="utf-8"))["repos"][0]
        self.assertNotIn("carried_over", persisted)
        self.assertTrue(advance["carried_over_cleared"])

    def test_carry_over_rejects_a_stale_baseline(self):
        self._write_json(self.state, {
            "from_sha": "c" * 40,
            "to_sha": "b" * 40,
            "reason": "manual_pause",
            "remaining_subsystems": ["one"],
        })

        with self.assertRaises(SystemExit):
            wiki_sync.cmd_carry_over(argparse.Namespace(
                config=str(self.config), repo="domain/repo", state=str(self.state)))


    def test_carry_over_allows_an_unfetched_repo(self):
        self._write_json(self.state, {
            "from_sha": "a" * 40,
            "reason": "not_started_after_0730",
            "remaining_subsystems": [],
        })

        result = self._run(wiki_sync.cmd_carry_over, argparse.Namespace(
            config=str(self.config), repo="domain/repo", state=str(self.state)))

        self.assertIsNone(result["carried_over"]["to_sha"])

    def test_complete_no_change_clears_carry_over(self):
        self._set_carry_over()
        self._write_changeset(status="no_change", to_sha="a" * 40)

        result = self._run(wiki_sync.cmd_complete_no_change, argparse.Namespace(
            config=str(self.config), repo="domain/repo", changeset=str(self.changeset)))

        persisted = json.loads(self.config.read_text(encoding="utf-8"))["repos"][0]
        self.assertNotIn("carried_over", persisted)
        self.assertTrue(result["carried_over_cleared"])

    def test_complete_no_change_rejects_non_final_status_and_retains_carry_over(self):
        self._set_carry_over()
        for status in ("changes", "error", "skipped_dirty"):
            with self.subTest(status=status):
                self._write_changeset(status=status, to_sha="a" * 40)
                with self.assertRaises(SystemExit):
                    wiki_sync.cmd_complete_no_change(argparse.Namespace(
                        config=str(self.config), repo="domain/repo",
                        changeset=str(self.changeset)))

        persisted = json.loads(self.config.read_text(encoding="utf-8"))["repos"][0]
        self.assertIn("carried_over", persisted)

    def test_complete_no_change_rejects_mismatched_sha_and_retains_carry_over(self):
        self._set_carry_over()
        self._write_changeset(status="no_change", to_sha="b" * 40)

        with self.assertRaises(SystemExit):
            wiki_sync.cmd_complete_no_change(argparse.Namespace(
                config=str(self.config), repo="domain/repo",
                changeset=str(self.changeset)))

        persisted = json.loads(self.config.read_text(encoding="utf-8"))["repos"][0]
        self.assertIn("carried_over", persisted)

    def _set_carry_over(self):
        config = json.loads(self.config.read_text(encoding="utf-8"))
        config["repos"][0]["carried_over"] = {
            "from_sha": "a" * 40,
            "to_sha": None,
            "reason": "not_started_after_0730",
            "remaining_subsystems": [],
        }
        self._write_json(self.config, config)

    def _write_changeset(self, status, to_sha):
        self._write_json(self.changeset, {
            "domain": "domain",
            "repo": "repo",
            "branch": "release",
            "from_sha": "a" * 40,
            "to_sha": to_sha,
            "status": status,
        })


class ConfigureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.code_root = self.root / "code"
        self.source = self.code_root / "domain" / "repo"
        (self.source / ".git").mkdir(parents=True)
        self.config = self.root / "config.json"
        self._write_json(self.config, {
            "code_root": str(self.code_root),
            "repos": [{
                "domain": "domain",
                "repo": "repo",
                "branch": "test",
                "last_synced_sha": "a" * 40,
                "last_synced_at": "2026-07-17T10:00:00+08:00",
                "carried_over": {"from_sha": "a" * 40},
            }],
        })

    @staticmethod
    def _write_json(path, value):
        path.write_text(json.dumps(value), encoding="utf-8")

    @staticmethod
    def _run(fn, args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            fn(args)
        return json.loads(output.getvalue())

    def test_configure_switches_branch_and_clears_stale_state(self):
        target = "b" * 40
        baseline = "a" * 40

        def fake_git(repo, args, **kwargs):
            if args[:3] == ["rev-parse", "--verify", baseline + "^{commit}"]:
                return 0, baseline + "\n"
            if args[:2] == ["merge-base", "--is-ancestor"]:
                return 0, ""
            raise AssertionError(args)

        with mock.patch.object(wiki_sync, "fetch_head", return_value=target), \
                mock.patch.object(wiki_sync, "run_git", side_effect=fake_git):
            result = self._run(wiki_sync.cmd_configure, argparse.Namespace(
                config=str(self.config), repo="domain/repo", branch="master",
                baseline=baseline))

        persisted = json.loads(self.config.read_text(encoding="utf-8"))["repos"][0]
        self.assertEqual("master", persisted["branch"])
        self.assertEqual(baseline, persisted["last_synced_sha"])
        self.assertNotIn("carried_over", persisted)
        self.assertNotIn("last_synced_at", persisted)
        self.assertEqual(target, result["target"])
        self.assertTrue(result["cleared_carry_over"])

    def test_configure_rejects_baseline_outside_target_branch(self):
        target = "b" * 40
        baseline = "a" * 40

        def fake_git(repo, args, **kwargs):
            if args[:3] == ["rev-parse", "--verify", baseline + "^{commit}"]:
                return 0, baseline + "\n"
            if args[:2] == ["merge-base", "--is-ancestor"]:
                return 1, ""
            raise AssertionError(args)

        with mock.patch.object(wiki_sync, "fetch_head", return_value=target), \
                mock.patch.object(wiki_sync, "run_git", side_effect=fake_git):
            with self.assertRaises(SystemExit):
                wiki_sync.cmd_configure(argparse.Namespace(
                    config=str(self.config), repo="domain/repo", branch="master",
                    baseline=baseline))

        persisted = json.loads(self.config.read_text(encoding="utf-8"))["repos"][0]
        self.assertEqual("test", persisted["branch"])
        self.assertEqual("a" * 40, persisted["last_synced_sha"])
        self.assertIn("carried_over", persisted)


if __name__ == "__main__":
    unittest.main()
