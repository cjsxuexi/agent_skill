#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""wiki_sync — deterministic collection layer for the nightly wiki sync.

Subcommands (always run with `python -X utf8`):

  init        Ensure D:\\wiki\\.wiki-sync.json exists and every enabled repo has a
              baseline last_synced_sha (= current origin/<branch> HEAD). Never
              overwrites an existing non-null baseline unless --force.
  configure   Explicitly set one repo's branch and historical baseline, after
              fetching the branch and verifying the baseline is an ancestor.
  collect     For each enabled repo: fetch origin/<branch>, range-diff
              last_synced_sha..origin/<branch> in ONE shot, map changed files to
              wiki subsystems via <WIKI_BASE>/<domain>/<repo>/.progress.json,
              classify noise / structural signals, and write one changeset JSON
              per repo plus a _run.json summary. Read-only w.r.t. source repos
              (fetch only; never touches the working tree).
  materialize Ensure the persistent linked worktree <sync_root>/<domain>/<repo>
              exists and is detached at the given SHA from `collect`. It never
              fetches and never modifies the D:\\code working-tree contents.
  carry-over  Persist an incomplete repo range in the config. The next collect
              exposes and prioritizes it; advance clears it after a full commit.
  complete-no-change
              Clear carry-over after a collected changeset proves the repo is
              still exactly at its baseline.
  advance     Set a repo's last_synced_sha in the config (call ONLY after the
              wiki commit for that repo succeeded).
  status      Print per-repo state (baseline, branch, enabled).

All JSON files are written UTF-8 (no BOM), ensure_ascii=False. .progress.json is
read with utf-8-sig because PowerShell-written files may carry a BOM.
"""

import argparse
import fnmatch
import io
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))

DEFAULT_CONFIG = r"D:\wiki\.wiki-sync.json"

NOISE_PATTERNS = [
    "*.lock", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "*.min.js", "*.min.css", "*.map",
    "*.png", "*.jpg", "*.jpeg", "*.gif", "*.ico", "*.svg", "*.webp",
    "*.jar", "*.class", "*.exe", "*.dll", "*.so", "*.zip", "*.tar.gz",
    "*.ttf", "*.woff", "*.woff2", "*.eot",
    ".idea/*", "*.iml", ".vscode/*",
    "node_modules/*", "dist/*", "build/*", "target/*", "out/*",
]

FETCH_TIMEOUT = 300
GIT_TIMEOUT = 120

# top-level dirs that are never code modules — excluded from the "new module"
# structural signal (their files still appear in `unmapped` for the report)
NON_MODULE_DIRS = {"docs", "doc", "sql", "scripts", "spec", "specs",
                   ".github", ".gitlab", "deploy", "ci"}


def now_iso():
    return datetime.now(CST).isoformat(timespec="seconds")


def run_git(repo, args, timeout=GIT_TIMEOUT, check=True):
    """Run git in `repo`, return (rc, stdout_str). Output decoded utf-8/replace."""
    cmd = ["git", "-C", repo, "-c", "core.quotepath=false"] + args
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RuntimeError("git timeout: %s" % " ".join(args))
    out = p.stdout.decode("utf-8", errors="replace")
    err = p.stderr.decode("utf-8", errors="replace")
    if check and p.returncode != 0:
        raise RuntimeError("git %s failed (rc=%d): %s" % (args[0], p.returncode, err.strip()[:500]))
    return p.returncode, out


def load_config(path):
    with io.open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def save_config(path, cfg):
    """Atomic write: temp file in same dir, then os.replace."""
    cfg["updated_at"] = now_iso()
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    try:
        with io.open(fd, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def load_carry_over_state(path):
    """Load and validate a UTF-8 JSON carry-over state file."""
    with io.open(path, encoding="utf-8-sig") as f:
        state = json.load(f)
    if not isinstance(state, dict):
        raise SystemExit("carry-over state must be a JSON object")
    required = ("from_sha", "reason", "remaining_subsystems")
    missing = [key for key in required if key not in state]
    if missing:
        raise SystemExit("carry-over state missing: %s" % ", ".join(missing))
    for key in ("from_sha", "reason"):
        if not isinstance(state[key], str) or not state[key].strip():
            raise SystemExit("carry-over %s must be a non-empty string" % key)
    to_sha = state.get("to_sha")
    if to_sha is not None and (not isinstance(to_sha, str) or not to_sha.strip()):
        raise SystemExit("carry-over to_sha must be null or a non-empty string")
    remaining = state["remaining_subsystems"]
    if not isinstance(remaining, list) or not all(
            isinstance(name, str) and name.strip() for name in remaining):
        raise SystemExit("carry-over remaining_subsystems must be a string array")
    normalized = {
        "from_sha": state["from_sha"].strip(),
        "to_sha": to_sha.strip() if to_sha is not None else None,
        "reason": state["reason"].strip(),
        "remaining_subsystems": list(dict.fromkeys(name.strip() for name in remaining)),
        "recorded_at": now_iso(),
    }
    if "detail" in state:
        if not isinstance(state["detail"], str):
            raise SystemExit("carry-over detail must be a string")
        normalized["detail"] = state["detail"]
    return normalized


def repo_key(r):
    return "%s/%s" % (r["domain"], r["repo"])


def find_repo(cfg, key):
    for r in cfg["repos"]:
        if repo_key(r) == key:
            return r
    raise SystemExit("repo not in config: %s" % key)


def source_path(cfg, r):
    return os.path.join(cfg["code_root"], r["domain"], r["repo"])


def worktree_path(cfg, r):
    return os.path.join(cfg["sync_root"], r["domain"], r["repo"])


def fetch_head(src, branch):
    """Fetch origin/<branch>; return the fetched tip SHA (via FETCH_HEAD)."""
    run_git(src, ["fetch", "origin", branch], timeout=FETCH_TIMEOUT)
    _, out = run_git(src, ["rev-parse", "FETCH_HEAD"])
    return out.strip()


def remote_tip_no_fetch(src, branch):
    rc, out = run_git(src, ["rev-parse", "refs/remotes/origin/" + branch], check=False)
    return out.strip() if rc == 0 else None


def is_noise(path, patterns):
    p = path.replace("\\", "/")
    for pat in patterns:
        if fnmatch.fnmatch(p, pat) or fnmatch.fnmatch(os.path.basename(p), pat):
            return True
        # directory-prefix patterns like "dist/*" should also match "web/dist/x.js"
        if pat.endswith("/*") and ("/" + pat[:-1]) in ("/" + p):
            return True
    return False


def load_doc_manifest(cfg, r):
    """Return (doc_mode, [(subsystem_name, norm_path_prefix)]).

    doc_mode: 'single' only when .progress.json explicitly says so; anything
    else (multi, missing mode key, legacy) is treated as multi, matching
    /document-systems' own rule. Missing file → (None, [])."""
    pj = os.path.join(cfg["wiki_base"], r["domain"], r["repo"], ".progress.json")
    if not os.path.exists(pj):
        return None, []
    with io.open(pj, encoding="utf-8-sig") as f:
        d = json.load(f)
    if d.get("mode") == "single":
        return "single", []
    subs = []
    for s in d.get("manifest", {}).get("subsystems", []):
        p = s.get("path", s["name"]).replace("\\", "/").strip("/")
        subs.append((s["name"], p))
    # longest prefix first so nested paths win
    subs.sort(key=lambda x: len(x[1]), reverse=True)
    return "multi", subs


def map_file(path, subs):
    p = path.replace("\\", "/")
    for name, prefix in subs:
        if p == prefix or p.startswith(prefix + "/"):
            return name
    return None


def collect_repo(cfg, r, no_fetch=False):
    key = repo_key(r)
    src = source_path(cfg, r)
    cs = {
        "domain": r["domain"], "repo": r["repo"], "branch": r["branch"],
        "source_path": src, "worktree_path": worktree_path(cfg, r),
        "from_sha": r.get("last_synced_sha"), "to_sha": None,
        "status": None, "history_rewritten": False, "commit_count": 0,
        "messages": [], "doc_mode": None, "subsystems": {}, "unmapped": [],
        "noise_count": 0, "noise_sample": [], "structural": [], "error": None,
        "carried_over": r.get("carried_over"), "carry_over_range_grew": False,
        "collected_at": now_iso(),
    }
    try:
        if not os.path.isdir(os.path.join(src, ".git")):
            raise RuntimeError("source repo missing or not a git repo: %s" % src)
        if no_fetch:
            new = remote_tip_no_fetch(src, r["branch"])
            if not new:
                raise RuntimeError("no remote-tracking ref for origin/%s (run without --no-fetch)" % r["branch"])
        else:
            new = fetch_head(src, r["branch"])
        cs["to_sha"] = new
        last = r.get("last_synced_sha")
        carried_over = r.get("carried_over")
        if carried_over and carried_over.get("from_sha") != last:
            raise RuntimeError("carried_over.from_sha does not match last_synced_sha")
        if carried_over:
            previous_to_sha = carried_over.get("to_sha")
            cs["carry_over_range_grew"] = (
                None if previous_to_sha is None else previous_to_sha != new)
        if not last:
            cs["status"] = "needs_baseline"
            return cs
        if last == new:
            cs["status"] = "no_change"
            return cs

        rc, _ = run_git(src, ["merge-base", "--is-ancestor", last, new], check=False)
        cs["history_rewritten"] = rc != 0

        _, cnt = run_git(src, ["rev-list", "--count", "%s..%s" % (last, new)], check=False)
        cs["commit_count"] = int(cnt.strip() or 0)

        _, msgs = run_git(src, ["log", "--no-merges", "--format=%h %s", "%s..%s" % (last, new)], check=False)
        cs["messages"] = [m for m in msgs.splitlines() if m.strip()][:200]

        # ONE whole-range comparison (net change), never per-commit
        _, ns = run_git(src, ["diff", "--name-status", "-M50", last, new])
        _, num = run_git(src, ["diff", "--numstat", last, new])
        stats = {}
        for line in num.splitlines():
            parts = line.split("\t")
            if len(parts) >= 3:
                a, d, p = parts[0], parts[1], parts[-1]
                stats[p] = (0 if a == "-" else int(a), 0 if d == "-" else int(d))

        doc_mode, subs = load_doc_manifest(cfg, r)
        cs["doc_mode"] = doc_mode
        patterns = cfg.get("noise_patterns", NOISE_PATTERNS)
        noise = []
        seen_new_topdirs = set()
        for line in ns.splitlines():
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            op = parts[0]
            path = parts[-1]  # rename lines: R<score>\told\tnew → take new
            if is_noise(path, patterns):
                noise.append(path)
                continue
            adds, dels = stats.get(path, (0, 0))
            entry = [op[0], path, adds, dels]
            if doc_mode == "single":
                bucket = cs["subsystems"].setdefault(r["repo"], {"files": [], "total_adds": 0, "total_dels": 0})
            else:
                name = map_file(path, subs)
                if name is None:
                    cs["unmapped"].append(entry)
                    if op[0] == "A" and "/" in path.replace("\\", "/"):
                        seen_new_topdirs.add(path.replace("\\", "/").split("/")[0])
                    continue
                bucket = cs["subsystems"].setdefault(name, {"files": [], "total_adds": 0, "total_dels": 0})
            bucket["files"].append(entry)
            bucket["total_adds"] += adds
            bucket["total_dels"] += dels

        cs["noise_count"] = len(noise)
        cs["noise_sample"] = noise[:20]

        # structural signals (multi mode only; single mode has one doc for everything)
        if doc_mode == "multi":
            known_tops = {p.split("/")[0] for _, p in subs}
            skip = set(cfg.get("non_module_dirs", [])) | NON_MODULE_DIRS
            new_modules = sorted(t for t in seen_new_topdirs
                                 if t not in known_tops and t.lower() not in skip)
            for t in new_modules:
                cs["structural"].append("new top-level dir not in manifest: %s/" % t)
            root_pom = [e for e in cs["unmapped"] if e[1].replace("\\", "/") == "pom.xml"]
            if root_pom:
                cs["structural"].append("root pom.xml changed (module list may have changed)")
        if doc_mode is None:
            cs["structural"].append("no .progress.json under wiki for this repo — run /document-systems first")
        if cs["history_rewritten"]:
            cs["structural"].append("history rewritten (force-push?): %s is not an ancestor of %s" % (last[:7], new[:7]))

        cs["status"] = "changes"
        return cs
    except Exception as e:
        cs["status"] = "error"
        cs["error"] = str(e)
        return cs


def cmd_init(args):
    if os.path.exists(args.config) and not args.force:
        cfg = load_config(args.config)
    else:
        cfg = None
    if cfg is None:
        raise SystemExit(
            "config not found: %s\n"
            "init expects the config file to exist with the repo list (create it once, "
            "last_synced_sha may be null); init only fills in null baselines." % args.config)
    changed = 0
    results = []
    for r in cfg["repos"]:
        key = repo_key(r)
        if not r.get("enabled", True):
            results.append({"repo": key, "status": "disabled"})
            continue
        if r.get("last_synced_sha") and not args.force:
            results.append({"repo": key, "status": "kept", "sha": r["last_synced_sha"]})
            continue
        try:
            sha = fetch_head(source_path(cfg, r), r["branch"])
            r["last_synced_sha"] = sha
            r["baselined_at"] = now_iso()
            r.pop("carried_over", None)
            changed += 1
            results.append({"repo": key, "status": "baselined", "sha": sha})
        except Exception as e:
            results.append({"repo": key, "status": "error", "error": str(e)})
    if changed:
        save_config(args.config, cfg)
    print(json.dumps({"config": args.config, "baselined": changed, "repos": results},
                     ensure_ascii=False, indent=2))


def cmd_configure(args):
    """Set one repo's branch and historical baseline as one explicit operation."""
    cfg = load_config(args.config)
    r = find_repo(cfg, args.repo)
    branch = args.branch.strip()
    baseline_arg = args.baseline.strip()
    if not branch:
        raise SystemExit("configure branch must be non-empty")
    if not re.fullmatch(r"[0-9a-fA-F]{7,40}", baseline_arg):
        raise SystemExit("configure baseline must be a 7-40 character commit SHA")

    src = source_path(cfg, r)
    if not os.path.isdir(os.path.join(src, ".git")):
        raise SystemExit("source repo missing or not a git repo: %s" % src)

    target = fetch_head(src, branch)
    _, baseline_out = run_git(src, ["rev-parse", "--verify", baseline_arg + "^{commit}"])
    baseline = baseline_out.strip()
    rc, _ = run_git(src, ["merge-base", "--is-ancestor", baseline, target], check=False)
    if rc != 0:
        raise SystemExit(
            "baseline %s is not an ancestor of origin/%s at %s" %
            (baseline, branch, target))

    old = {
        "branch": r.get("branch"),
        "last_synced_sha": r.get("last_synced_sha"),
        "carried_over": bool(r.get("carried_over")),
        "last_synced_at": r.get("last_synced_at"),
    }
    r["branch"] = branch
    r["last_synced_sha"] = baseline
    r["baselined_at"] = now_iso()
    r.pop("carried_over", None)
    r.pop("last_synced_at", None)
    save_config(args.config, cfg)
    print(json.dumps({
        "config": args.config,
        "repo": args.repo,
        "branch": branch,
        "baseline": baseline,
        "target": target,
        "old": old,
        "cleared_carry_over": old["carried_over"],
    }, ensure_ascii=False, indent=2))


def cmd_collect(args):
    cfg = load_config(args.config)
    os.makedirs(args.out, exist_ok=True)
    targets = [r for r in cfg["repos"] if r.get("enabled", True)]
    if args.repo:
        targets = [find_repo(cfg, args.repo)]
    else:
        targets.sort(key=lambda r: 0 if r.get("carried_over") else 1)
    summary = {"started_at": now_iso(), "config": args.config,
               "out": os.path.abspath(args.out), "repos": []}
    for r in targets:
        cs = collect_repo(cfg, r, no_fetch=args.no_fetch)
        fname = "%s__%s.json" % (r["domain"], r["repo"])
        fpath = os.path.join(args.out, fname)
        with io.open(fpath, "w", encoding="utf-8") as f:
            json.dump(cs, f, ensure_ascii=False, indent=2)
        summary["repos"].append({
            "repo": repo_key(r), "status": cs["status"], "commit_count": cs["commit_count"],
            "subsystems": sorted(cs["subsystems"].keys()), "structural": len(cs["structural"]),
            "unmapped": len(cs["unmapped"]), "changeset": fname,
            "carried_over": bool(cs["carried_over"]),
            "carry_over_range_grew": cs["carry_over_range_grew"],
            "error": cs["error"],
        })
    summary["finished_at"] = now_iso()
    with io.open(os.path.join(args.out, "_run.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def cmd_materialize(args):
    cfg = load_config(args.config)
    r = find_repo(cfg, args.repo)
    src = source_path(cfg, r)
    wt = worktree_path(cfg, r)
    sha = args.sha
    if os.path.isdir(wt) and os.path.exists(os.path.join(wt, ".git")):
        rc, _ = run_git(wt, ["rev-parse", "--is-inside-work-tree"], check=False)
        if rc == 0:
            run_git(wt, ["checkout", "--detach", sha], timeout=FETCH_TIMEOUT)
            print(json.dumps({"worktree": wt, "sha": sha, "action": "updated"}, ensure_ascii=False))
            return
        raise SystemExit("path exists but is not a usable worktree: %s (remove it manually)" % wt)
    if os.path.isdir(wt) and os.listdir(wt):
        raise SystemExit("path exists and is not empty, refusing: %s" % wt)
    os.makedirs(os.path.dirname(wt), exist_ok=True)
    run_git(src, ["worktree", "prune"], check=False)
    run_git(src, ["worktree", "add", "--detach", wt, sha], timeout=FETCH_TIMEOUT)
    print(json.dumps({"worktree": wt, "sha": sha, "action": "created"}, ensure_ascii=False))


def cmd_carry_over(args):
    cfg = load_config(args.config)
    r = find_repo(cfg, args.repo)
    state = load_carry_over_state(args.state)
    baseline = r.get("last_synced_sha")
    if state["from_sha"] != baseline:
        raise SystemExit(
            "carry-over from_sha does not match last_synced_sha: %s" % baseline)
    if state["to_sha"] is not None and state["to_sha"] == baseline:
        raise SystemExit("carry-over to_sha must differ from last_synced_sha")
    replaced = bool(r.get("carried_over"))
    r["carried_over"] = state
    save_config(args.config, cfg)
    print(json.dumps({"repo": args.repo, "carried_over": state, "replaced": replaced},
                     ensure_ascii=False, indent=2))


def cmd_complete_no_change(args):
    """Clear carry-over only from a validated no-change collection result."""
    cfg = load_config(args.config)
    r = find_repo(cfg, args.repo)
    with io.open(args.changeset, encoding="utf-8-sig") as f:
        changeset = json.load(f)
    if not isinstance(changeset, dict):
        raise SystemExit("changeset must be a JSON object")

    changeset_repo = "%s/%s" % (changeset.get("domain"), changeset.get("repo"))
    if changeset_repo != args.repo:
        raise SystemExit("changeset repo does not match requested repo: %s" % changeset_repo)
    if changeset.get("branch") != r.get("branch"):
        raise SystemExit("changeset branch does not match configured branch: %s" % r.get("branch"))
    if changeset.get("status") != "no_change":
        raise SystemExit("carry-over can only be completed from a no_change changeset")

    baseline = r.get("last_synced_sha")
    if not baseline:
        raise SystemExit("cannot complete carry-over without last_synced_sha")
    if changeset.get("from_sha") != baseline or changeset.get("to_sha") != baseline:
        raise SystemExit("no_change changeset SHA does not match last_synced_sha: %s" % baseline)

    carried_over = r.get("carried_over")
    if carried_over and carried_over.get("from_sha") != baseline:
        raise SystemExit("carried_over.from_sha does not match last_synced_sha")
    cleared = bool(r.pop("carried_over", None))
    if cleared:
        save_config(args.config, cfg)
    print(json.dumps({"repo": args.repo, "status": "no_change",
                      "carried_over_cleared": cleared}, ensure_ascii=False))


def cmd_advance(args):
    cfg = load_config(args.config)
    r = find_repo(cfg, args.repo)
    old = r.get("last_synced_sha")
    r["last_synced_sha"] = args.sha
    r["last_synced_at"] = now_iso()
    cleared = bool(r.pop("carried_over", None))
    save_config(args.config, cfg)
    print(json.dumps({"repo": args.repo, "from": old, "to": args.sha,
                      "carried_over_cleared": cleared}, ensure_ascii=False))


def cmd_status(args):
    cfg = load_config(args.config)
    rows = [{"repo": repo_key(r), "branch": r["branch"], "enabled": r.get("enabled", True),
             "last_synced_sha": r.get("last_synced_sha"), "last_synced_at": r.get("last_synced_at"),
             "carried_over": r.get("carried_over")}
            for r in cfg["repos"]]
    rows.sort(key=lambda row: 0 if row["carried_over"] else 1)
    print(json.dumps({"config": args.config, "repos": rows}, ensure_ascii=False, indent=2))


def main():
    ap = argparse.ArgumentParser(prog="wiki_sync")
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="fill null baselines with current origin/<branch> HEAD")
    p.add_argument("--force", action="store_true", help="re-baseline ALL repos (discards pending ranges)")
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("configure", help="set one repo's branch and historical baseline")
    p.add_argument("--repo", required=True)
    p.add_argument("--branch", required=True)
    p.add_argument("--baseline", required=True, help="historical commit SHA (7-40 hex characters)")
    p.set_defaults(fn=cmd_configure)

    p = sub.add_parser("collect", help="fetch + one-shot range diff -> changeset JSON per repo")
    p.add_argument("--out", required=True)
    p.add_argument("--repo", help="domain/repo — limit to one repo")
    p.add_argument("--no-fetch", action="store_true", help="use existing remote-tracking refs")
    p.set_defaults(fn=cmd_collect)

    p = sub.add_parser("materialize", help="ensure persistent detached worktree for a repo")
    p.add_argument("--repo", required=True)
    p.add_argument("--sha", required=True, help="exact to_sha emitted by collect")
    p.set_defaults(fn=cmd_materialize)

    p = sub.add_parser("carry-over", help="persist an incomplete repo range from a JSON state file")
    p.add_argument("--repo", required=True)
    p.add_argument("--state", required=True, help="UTF-8 JSON state file")
    p.set_defaults(fn=cmd_carry_over)

    p = sub.add_parser("complete-no-change",
                       help="clear carry-over from a validated no_change changeset")
    p.add_argument("--repo", required=True)
    p.add_argument("--changeset", required=True, help="changeset JSON emitted by collect")
    p.set_defaults(fn=cmd_complete_no_change)

    p = sub.add_parser("advance", help="record last_synced_sha AFTER the wiki commit succeeded")
    p.add_argument("--repo", required=True)
    p.add_argument("--sha", required=True)
    p.set_defaults(fn=cmd_advance)

    p = sub.add_parser("status", help="print per-repo sync state")
    p.set_defaults(fn=cmd_status)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
