# -*- coding: utf-8 -*-
"""Orchestrator + CLI: JSONL -> ``<export_root>/<date>_<slug>_<id8>/`` deliverables,
then recompute the cross-session index.

Deterministic: the export directory name derives from session *content* (first
timestamp + title), and ``exported_at`` is injected, so a fixed ``exported_at``
yields byte-identical output (design §14).
"""
import argparse
import json
import os
import sys
from pathlib import Path

from . import config, parse, render, summarize, catalog, index

DEFAULT_TRUNCATE_AT = render.DEFAULT_TRUNCATE_AT


def _subagents_dir(main_jsonl):
    main_jsonl = Path(main_jsonl)
    return main_jsonl.parent / main_jsonl.stem / "subagents"


def _discover_subagents(main_jsonl):
    """Find ``agent-*.jsonl`` sidechains and their parent ``toolUseId`` (via .meta.json)."""
    sub_dir = _subagents_dir(main_jsonl)
    out = []
    if not sub_dir.is_dir():
        return out
    for agent_jsonl in sorted(sub_dir.glob("agent-*.jsonl")):
        tool_use_id = ""
        meta = agent_jsonl.with_suffix(".meta.json")
        if meta.is_file():
            try:
                tool_use_id = json.loads(meta.read_text(encoding="utf-8")).get("toolUseId", "")
            except (ValueError, OSError):
                tool_use_id = ""
        out.append({"path": agent_jsonl, "stem": agent_jsonl.stem, "tool_use_id": tool_use_id})
    return out


def _write_rendered(base_dir, md, raw_files, md_name):
    config.write_text(Path(base_dir) / md_name, md)
    for rel, content in raw_files.items():
        config.write_text(Path(base_dir) / rel, content)


def export_session(jsonl_path, export_root, exported_at="", no_raw=False,
                   truncate_at=DEFAULT_TRUNCATE_AT):
    """Export one session (main + linked sub-agents) into its own export dir."""
    jsonl_path = Path(jsonl_path)
    session = parse.parse_session(jsonl_path)
    summary = summarize.summarize(session, exported_at=exported_at)

    subagents = _discover_subagents(jsonl_path)
    subagent_links = {}
    for sub in subagents:
        rel = "subagents/%s.md" % sub["stem"]
        if sub["tool_use_id"]:
            subagent_links[sub["tool_use_id"]] = rel

    first_ts = summary["first_timestamp"]
    date = first_ts[:10] if first_ts else "0000-00-00"
    dirname = "%s_%s_%s" % (date, config.slugify(session.title), session.session_id[:8])
    export_dir = Path(export_root) / dirname
    export_dir.mkdir(parents=True, exist_ok=True)

    md, raw_files = render.render_transcript(
        session, exported_at=exported_at, no_raw=no_raw,
        truncate_at=truncate_at, subagent_links=subagent_links)
    _write_rendered(export_dir, md, raw_files, "transcript.md")
    config.write_json(export_dir / "summary.json", summary)

    written_subs = []
    for sub in subagents:
        sub_session = parse.parse_session(sub["path"])
        sub_md, sub_raw = render.render_transcript(
            sub_session, exported_at=exported_at, no_raw=no_raw, truncate_at=truncate_at)
        _write_rendered(export_dir / "subagents", sub_md, sub_raw, "%s.md" % sub["stem"])
        written_subs.append(sub["stem"])

    return {
        "export_dir": export_dir,
        "transcript_path": export_dir / "transcript.md",
        "summary_path": export_dir / "summary.json",
        "raw_files": sorted(raw_files.keys()),
        "subagents": written_subs,
    }


def locate_session(projects_root, session_id):
    """Find ``<projects_root>/<proj>/<session_id>.jsonl`` (top-level only)."""
    matches = sorted(Path(projects_root).glob("*/%s.jsonl" % session_id))
    if not matches:
        raise FileNotFoundError("session %s not found under %s" % (session_id, projects_root))
    return matches[0]


def _now_iso():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="session_export",
                                 description="Claude Code session export + D1/D2 analysis engine")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pe = sub.add_parser("export", help="export one session, then rebuild the index")
    pe.add_argument("--jsonl")
    pe.add_argument("--session-id")
    pe.add_argument("--projects-root")
    pe.add_argument("--export-root", default=config.DEFAULT_EXPORT_ROOT)
    pe.add_argument("--exported-at", default=None)
    pe.add_argument("--no-raw", action="store_true")
    pe.add_argument("--truncate-at", type=int, default=DEFAULT_TRUNCATE_AT)

    pi = sub.add_parser("index", help="recompute INDEX.md / index.json from summaries")
    pi.add_argument("--export-root", default=config.DEFAULT_EXPORT_ROOT)
    pi.add_argument("--exported-at", default=None)

    pc = sub.add_parser("catalog", help="list top-level sessions under a projects root")
    pc.add_argument("--projects-root", required=True)
    pc.add_argument("--export-root")

    pa = sub.add_parser("analyze",
                        help="launcher: guardrails + export + score + wiki_touch + D1/D2 analysis + eval-log")
    pa.add_argument("--session-id", help="hook path: the finished session to analyse")
    pa.add_argument("--jsonl", help="analyse this jsonl directly (skips projects-root lookup)")
    pa.add_argument("--from-hook-stdin", action="store_true",
                    help="read a SessionEnd hook JSON payload from stdin for jsonl/session_id")
    pa.add_argument("--issue-id", help="comment path: resolve session_id from `multica issue runs`")
    pa.add_argument("--projects-root")
    pa.add_argument("--export-root", default=config.DEFAULT_EXPORT_ROOT)
    pa.add_argument("--wiki-root", default=config.DEFAULT_WIKI_ROOT)
    pa.add_argument("--trigger", default="session_end_hook",
                    choices=["comment", "session_end_hook", "schedule_poll"])
    pa.add_argument("--trigger-comment-id", default="")
    pa.add_argument("--exported-at", default=None)
    pa.add_argument("--generated-at", default=None)
    pa.add_argument("--no-raw", action="store_true")
    pa.add_argument("--truncate-at", type=int, default=DEFAULT_TRUNCATE_AT)
    pa.add_argument("--self-session-id", action="append", default=[],
                    help="export-session's own session_id(s) to exclude (§12); repeatable")
    pa.add_argument("--self-agent-id", default=None)
    pa.add_argument("--eval-log", default=None)

    args = ap.parse_args(argv)

    if args.cmd == "export":
        exported_at = args.exported_at if args.exported_at is not None else _now_iso()
        if args.jsonl:
            jsonl = Path(args.jsonl)
        elif args.session_id and args.projects_root:
            jsonl = locate_session(args.projects_root, args.session_id)
        else:
            ap.error("export needs --jsonl or (--session-id and --projects-root)")
        res = export_session(jsonl, args.export_root, exported_at=exported_at,
                             no_raw=args.no_raw, truncate_at=args.truncate_at)
        index.build_index(args.export_root, exported_at=exported_at)
        print(str(res["export_dir"]))
        return 0

    if args.cmd == "index":
        exported_at = args.exported_at if args.exported_at is not None else _now_iso()
        ix, _ = index.build_index(args.export_root, exported_at=exported_at)
        print("indexed %d sessions" % ix["session_count"])
        return 0

    if args.cmd == "catalog":
        cache = Path(args.export_root) / ".catalog-cache.json" if args.export_root else None
        metas = catalog.catalog(args.projects_root, cache_path=cache)
        print("found %d sessions" % len(metas))
        return 0

    if args.cmd == "analyze":
        from . import launcher                      # lazy: avoids export<->launcher import cycle
        exported_at = args.exported_at if args.exported_at is not None else _now_iso()
        generated_at = args.generated_at if args.generated_at is not None else exported_at
        projects_root = args.projects_root or str(config.detect_projects_root(os.environ))
        self_sids = set(args.self_session_id)

        jsonl = args.jsonl
        session_id = args.session_id
        if args.from_hook_stdin:
            payload = launcher.parse_hook_payload(sys.stdin.read())
            jsonl = jsonl or payload.get("jsonl_path")
            session_id = session_id or payload.get("session_id")
        if not jsonl and not session_id and args.issue_id:
            runs = _fetch_issue_runs(args.issue_id)
            session_id = launcher.resolve_session_id(
                runs, self_agent_id=args.self_agent_id, self_session_ids=self_sids)
            if not session_id:
                ap.error("could not resolve a work session_id from `multica issue runs %s`" % args.issue_id)
        if not jsonl and not session_id:
            ap.error("analyze needs --jsonl, --session-id, --issue-id, or --from-hook-stdin")

        res = launcher.run(
            jsonl_path=jsonl, session_id=(None if jsonl else session_id),
            projects_root=(None if jsonl else projects_root), export_root=args.export_root,
            wiki_root=args.wiki_root, trigger=args.trigger,
            trigger_comment_id=args.trigger_comment_id, exported_at=exported_at,
            generated_at=generated_at, no_raw=args.no_raw, truncate_at=args.truncate_at,
            self_session_ids=self_sids, eval_log_path=args.eval_log)
        if res["skipped"]:
            print("skipped: " + res["reason"])
            return 0
        print(str(res["analysis_path"]))
        return 0

    return 2


def _fetch_issue_runs(issue_id):
    """Shell out to the authenticated Multica CLI for this issue's run history (comment path)."""
    import subprocess
    out = subprocess.check_output(
        ["multica", "issue", "runs", issue_id, "--output", "json"],
        text=True, encoding="utf-8")
    return json.loads(out)


if __name__ == "__main__":
    sys.exit(main())
