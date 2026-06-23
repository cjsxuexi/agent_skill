"""Command-line entry point (plan §6.2, §6.8).

Every subcommand prints exactly one JSON object to stdout and exits with the mapped code:
    0 ok / 2 usage / 3 rejected / 4 addr / 5 coupling / 6 stale / 7 parse / 8 io / 9 source / 10 need-domain.
``lint`` exits 0 even with findings (findings are the product); ``--strict`` exits 3 when
any ERROR is present. On an EngineError, the process prints ``{code, message_zh[, detail]}``
and exits with ``EngineError.exit_code``.

Runnable BOTH as ``python -X utf8 <path>/cli.py <args>`` and ``python -m wiki_engine.cli``:
when run as a script (no package context) the bootstrap below puts the ``scripts/`` dir on
sys.path so ``from wiki_engine ...`` resolves either way.
"""

import argparse
import json
import os
import sys

# --- bootstrap: make `from wiki_engine ...` work when run as a loose script ---
if __package__ in (None, ""):
    _HERE = os.path.dirname(os.path.abspath(__file__))      # .../wiki_engine
    _SCRIPTS = os.path.dirname(_HERE)                        # .../scripts
    if _SCRIPTS not in sys.path:
        sys.path.insert(0, _SCRIPTS)

from wiki_engine import io_utf8, parser, doc_kind, questions, refs, lint  # noqa: E402
from wiki_engine.errors import EngineError, UsageError, EXIT_OK, EXIT_REJECTED  # noqa: E402
from wiki_engine.lint.base import LintContext, ERROR  # noqa: E402
from wiki_engine.txn import Transaction  # noqa: E402


def _emit(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False, indent=2))
    sys.stdout.write("\n")


def _iter_md(path, recursive):
    if os.path.isfile(path):
        yield path
        return
    if recursive:
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for f in sorted(files):
                if f.endswith(".md"):
                    yield os.path.join(root, f)
    else:
        for f in sorted(os.listdir(path)):
            if f.endswith(".md"):
                yield os.path.join(path, f)


def _rel_to_root(path, doc_root):
    return os.path.relpath(path, doc_root).replace("\\", "/")


# ===========================================================================
def cmd_outline(args):
    text = io_utf8.read_text(args.path)
    doc = parser.parse(args.path, text)
    sections = []
    for s in doc.sections:
        sections.append({
            "number": s.number, "title": s.title, "anchor": s.anchor,
            "start": s.start, "end": s.end,
            "children": [{"level": c.level, "number": c.number, "title": c.title,
                          "anchor": c.anchor} for c in s.children],
        })
    _emit({"path": args.path, "frontmatter": doc.frontmatter.kind,
           "preamble_end": doc.preamble_end, "sections": sections})
    return EXIT_OK


def cmd_questions(args):
    # The qid namespace is the doc path RELATIVE TO doc_root — it MUST match the `target`
    # used by `apply` (e.g. "port-data/architecture.md"), or resolve_question can't find the
    # entry. Pass --doc-root for a single-file query; a directory --path is itself the doc_root.
    if args.doc_root:
        doc_root = args.doc_root
    elif os.path.isdir(args.path):
        doc_root = args.path
    else:
        doc_root = os.path.dirname(args.path)
    out = []
    for md in _iter_md(args.path, args.recursive):
        rel = _rel_to_root(md, doc_root)
        text = io_utf8.read_text(md)
        doc = parser.parse(md, text)
        for q in questions.enumerate_questions(rel, doc):
            out.append({"doc": rel, "qid": q.qid, "locator": q.locator,
                        "first_sentence": q.first_sentence})
    _emit({"path": args.path, "questions": out})
    return EXIT_OK


def cmd_lint(args):
    if os.path.isdir(args.path):
        doc_root = args.path
    else:
        doc_root = args.source_root_doc or os.path.dirname(os.path.abspath(args.path))
    rules_filter = set(args.rules.split(",")) if args.rules else None
    all_findings = []
    for md in _iter_md(args.path, args.recursive):
        rel = _rel_to_root(md, doc_root)
        text = io_utf8.read_text(md)
        kind = doc_kind.classify(rel, text)
        if kind == doc_kind.DocKind.IGNORED:
            continue
        doc = parser.parse(md, text)
        ctx = LintContext(rel, doc, kind, doc_root=doc_root, source_root=args.source_root)
        for f in lint.run_lint(ctx):
            if rules_filter and f.rule_id not in rules_filter:
                continue
            all_findings.append(f)
    has_err = any(f.severity == ERROR for f in all_findings)
    payload = {"path": args.path, "findings": [f.to_dict() for f in all_findings],
               "count": len(all_findings), "has_error": has_err}
    _emit(payload)
    if args.strict and has_err:
        return EXIT_REJECTED
    return EXIT_OK


def cmd_apply(args):
    txn_path = os.path.abspath(args.txn)
    spec = json.loads(io_utf8.read_text(txn_path))
    base_dir = os.path.dirname(txn_path)
    doc_root = spec.get("doc_root")
    if not doc_root:
        raise UsageError("事务 JSON 缺少 doc_root", code="E_USAGE")
    source_root = args.source_root or spec.get("source_root")
    txn = Transaction(doc_root=doc_root, source_root=source_root, base_dir=base_dir,
                      ops_json=spec.get("ops", []), install_root=args.install_root)
    result = txn.run(dry_run=args.dry_run)
    _emit(result)
    return EXIT_OK


def cmd_init_common(args):
    from wiki_engine import ops as ops_mod

    class _MiniTxn:
        def __init__(self, doc_root, install_root):
            self.doc_root = doc_root
            self.install_root = install_root

    doc_root = args.doc_root
    if args.level == "global":
        if not args.wiki_base:
            raise UsageError("global 级别需 --wiki-base", code="E_USAGE")
        # dirname(dirname(doc_root)) 须等于 wiki_base（三级 _common_target_path）
        doc_root = os.path.join(args.wiki_base, "_d", "_placeholder")
    elif args.level == "domain":
        if not (args.wiki_base and args.domain):
            raise UsageError("domain 级别需 --wiki-base 与 --domain", code="E_USAGE")
        # dirname(doc_root) 须等于 <wiki_base>/<domain>
        doc_root = os.path.join(args.wiki_base, args.domain, "_placeholder")
    elif not doc_root:
        raise UsageError("repo 级别需 --doc-root", code="E_USAGE")

    install_root = args.install_root
    inst = install_root or os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))
    tpl_path = os.path.join(inst, "references", "templates", "common-{}.md".format(args.type))
    if not os.path.exists(tpl_path):
        raise UsageError("找不到模板 common-{}.md".format(args.type), code="E_USAGE")
    tpl = ops_mod._strip_leading_comment(io_utf8.read_text(tpl_path))
    level_zh = {"repo": "仓库级", "domain": "域级", "global": "全局"}.get(args.level, args.level)
    content = (tpl.replace("<LEVEL>", args.level)
                  .replace("<OWNS>", args.name)
                  .replace("<TITLE>", args.name)
                  .replace("<SCOPE_BODY>", "{}公共文档。".format(level_zh))
                  .replace("<TYPE_BODY>", "（待补充）")
                  .replace("<QUESTIONS>", "无"))
    mt = _MiniTxn(doc_root, install_root)
    abspath, rel_display = ops_mod._common_target_path(mt, args.level, args.name)
    base = os.path.dirname(os.path.dirname(abspath))
    if not os.path.isdir(base):
        raise UsageError("目标目录不存在：{}（请先建立该仓/域/wiki 目录）".format(base),
                         code="E_USAGE")
    if os.path.exists(abspath):
        raise UsageError("目标已存在：{}".format(abspath), code="E_USAGE")
    io_utf8.write_text(abspath, content)
    _emit({"status": "ok", "created": abspath, "rel": rel_display,
           "message_zh": "已从模板生成 common 文档：{}".format(rel_display)})
    return EXIT_OK


def cmd_refs(args):
    doc_root = args.scope_root or os.path.dirname(os.path.abspath(args.path))
    scope_root = doc_root
    if args.scope == "wiki":
        scope_root = os.path.dirname(os.path.normpath(doc_root))
    results = refs.compute_refs(args.path, scope_root, anchor=args.anchor)
    _emit({"path": args.path, "anchor": args.anchor, "scope": args.scope,
           "referrers": results, "count": len(results)})
    return EXIT_OK


def cmd_rule_catalog(args):
    _emit({"rules": lint.rule_catalog()})
    return EXIT_OK


def cmd_resolve_domain(args):
    from wiki_engine import registry
    _emit(registry.resolve(args.wiki, args.repo, set_domain=args.set_domain))
    return EXIT_OK


def cmd_update_domain_index(args):
    from wiki_engine import domain_index
    path = domain_index.write_index(args.wiki, args.domain)
    _emit({"status": "ok", "domain": args.domain, "index": path,
           "message_zh": "已生成域索引：{}".format(path)})
    return EXIT_OK


# ===========================================================================
class _JsonArgumentParser(argparse.ArgumentParser):
    """Emit a JSON usage error (and exit 2) instead of argparse's stderr text, so every
    invocation — including a bad one — prints one JSON object the skill can parse."""

    def error(self, message):
        _emit({"code": "E_USAGE", "message_zh": "命令行参数错误：{}".format(message)})
        raise SystemExit(2)


def build_parser():
    p = _JsonArgumentParser(prog="wiki_engine", description="wiki-engine CLI")
    sub = p.add_subparsers(dest="cmd")

    o = sub.add_parser("outline")
    o.add_argument("--path", required=True)
    o.set_defaults(func=cmd_outline)

    q = sub.add_parser("questions")
    q.add_argument("--path", required=True)
    q.add_argument("--recursive", action="store_true")
    q.add_argument("--doc-root", dest="doc_root", default=None,
                   help="doc_root for the qid namespace (must match apply's target rel)")
    q.set_defaults(func=cmd_questions)

    l = sub.add_parser("lint")
    l.add_argument("--path", required=True)
    l.add_argument("--recursive", action="store_true")
    l.add_argument("--source-root", dest="source_root", default=None)
    l.add_argument("--doc-root", dest="source_root_doc", default=None,
                   help="doc_root for single-file lint (link resolution base)")
    l.add_argument("--strict", action="store_true")
    l.add_argument("--rules", default=None)
    l.set_defaults(func=cmd_lint)

    a = sub.add_parser("apply")
    a.add_argument("--txn", required=True)
    a.add_argument("--dry-run", dest="dry_run", action="store_true")
    a.add_argument("--source-root", dest="source_root", default=None)
    a.add_argument("--install-root", dest="install_root", default=None)
    a.set_defaults(func=cmd_apply)

    ic = sub.add_parser("init-common")
    ic.add_argument("--level", required=True, choices=["repo", "domain", "global"])
    ic.add_argument("--name", required=True)
    ic.add_argument("--type", required=True, choices=["glossary", "shared-lib", "protocol", "infra"])
    ic.add_argument("--doc-root", dest="doc_root", default=None)
    ic.add_argument("--wiki-base", dest="wiki_base", default=None)
    ic.add_argument("--domain", dest="domain", default=None)
    ic.add_argument("--install-root", dest="install_root", default=None)
    ic.set_defaults(func=cmd_init_common)

    r = sub.add_parser("refs")
    r.add_argument("--path", required=True)
    r.add_argument("--anchor", default=None)
    r.add_argument("--scope", choices=["doc-root", "wiki"], default="doc-root")
    r.add_argument("--scope-root", dest="scope_root", default=None)
    r.set_defaults(func=cmd_refs)

    rc = sub.add_parser("rule-catalog")
    rc.set_defaults(func=cmd_rule_catalog)

    rd = sub.add_parser("resolve-domain")
    rd.add_argument("--repo", required=True)
    rd.add_argument("--wiki", required=True)
    rd.add_argument("--set", dest="set_domain", default=None)
    rd.set_defaults(func=cmd_resolve_domain)

    udi = sub.add_parser("update-domain-index")
    udi.add_argument("--wiki", required=True)
    udi.add_argument("--domain", required=True)
    udi.set_defaults(func=cmd_update_domain_index)

    return p


def main(argv=None):
    parser_ = build_parser()
    try:
        args = parser_.parse_args(argv)
    except SystemExit as exc:
        # _JsonArgumentParser.error already emitted JSON; --help exits 0 (help on stdout)
        return exc.code if isinstance(exc.code, int) else 2
    if not getattr(args, "func", None):
        _emit({"code": "E_USAGE", "message_zh": "缺少子命令"})
        return 2
    try:
        return args.func(args)
    except EngineError as exc:
        _emit(exc.to_dict())
        return exc.exit_code
    except FileNotFoundError as exc:
        _emit({"code": "E_IO", "message_zh": "文件不存在：{}".format(exc)})
        return 8
    except json.JSONDecodeError as exc:
        _emit({"code": "E_USAGE", "message_zh": "JSON 解析失败：{}".format(exc)})
        return 2
    except Exception as exc:  # never crash without emitting JSON (the skill parses stdout)
        _emit({"code": "E_ENGINE",
               "message_zh": "内部错误：{}（{}）".format(type(exc).__name__, str(exc)[:200])})
        return 8


if __name__ == "__main__":
    sys.exit(main())
