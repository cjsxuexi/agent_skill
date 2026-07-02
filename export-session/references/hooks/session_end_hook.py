# -*- coding: utf-8 -*-
"""SessionEnd hook entry — analyse the just-finished local Claude Code session
(design §6 "真·全自动"). Wire it from ``settings.json`` (see ``../triggers.md``).

The hook feeds a JSON payload on stdin (``session_id`` + ``transcript_path``);
``analyze --from-hook-stdin`` reads it, then the launcher applies the §12/§13
guardrails (a session whose cwd is the export-session skill itself is skipped, so
this never analyses its own analysis run).

Override the roots with env vars ``EXPORT_SESSION_ROOT`` / ``EXPORT_SESSION_WIKI_ROOT``.
"""
import os
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from session_export import export  # noqa: E402


def main():
    argv = [
        "analyze", "--from-hook-stdin", "--trigger", "session_end_hook",
        "--export-root", os.environ.get("EXPORT_SESSION_ROOT", "D:\\claude-sessions"),
        "--wiki-root", os.environ.get("EXPORT_SESSION_WIKI_ROOT", "D:\\wiki"),
    ]
    return export.main(argv)


if __name__ == "__main__":
    sys.exit(main())
