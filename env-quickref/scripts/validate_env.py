#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only validator for a 港口环境实例信息 doc (<WIKI_BASE>/<域>/_env/<港口>.md).

Exit 0 = OK (may carry warnings); exit 2 = hard fail. Prints a JSON summary to stdout.
Hard fails (block a write): unreadable file, missing/incomplete frontmatter
(port/domain/updated), `???` mojibake, an H2 outside {test, Pre-release, prod,
待确认...}, a missing env H2, an instance H3 without the `<env> · ` prefix of its
enclosing env section, a duplicate H3 heading (anchors must stay unique), or a
credential-looking value (password/token/密码 followed by = or :) — the doc stores
only pointers, never secrets.
Style issues (instance section without a `> 来源：` line) are warnings only.

Usage:
  python -X utf8 validate_env.py <path-to-_env/<港口>.md>
  python -X utf8 validate_env.py <path> --check-refs [--wiki-base <dir>]

--check-refs: reverse-grep every `_env/<港口>.md#anchor` reference across the wiki
and verify each anchor still resolves against this file's headings (GitHub-exact
slugs). `_env/` is an engine-IGNORED area with no lint coverage, so this is the
only anchor protection inbound links get. Without --wiki-base the wiki root is
derived from the file path (<wiki>/<域>/_env/<port>.md → two levels up from _env).
"""
import io
import json
import os
import re
import sys
import unicodedata

ENVS = ("test", "Pre-release", "prod")
H1_RE = re.compile(r"^# \S")
H2_RE = re.compile(r"^## (.+)$")
H3_RE = re.compile(r"^### (.+)$")
# secrets: latin keywords or 密码, immediately followed by a separator and a value
CRED_RE = re.compile(
    r"(?i)(password|passwd|pwd|secret|api[-_]?key|token)\s*[=:：]\s*\S"
    r"|密码\s*[=:：]\s*\S")
SOURCE_RE = re.compile(r"^>\s*来源：")


def _is_word_char(ch):
    # replicated from wiki_engine slug.py (GitHub-exact slugger); keep in sync,
    # fold into one shared module when this skill merges with prod-issue-quickref
    cat = unicodedata.category(ch)
    return cat[0] in ("L", "M") or cat == "Nd" or cat == "Pc"


def slug(text):
    kept = []
    for ch in text.lower():
        if ch == " " or ch == "-" or _is_word_char(ch):
            kept.append(ch)
    return "".join(kept).replace(" ", "-")


def heading_slugs(text):
    """All heading anchors of the doc, de-duplicated github-slugger style."""
    occurrences = {}
    out = set()
    for ln in text.splitlines():
        m = re.match(r"^(#{1,6}) (.+)$", ln)
        if not m:
            continue
        base = slug(m.group(2).strip())
        result = base
        while result in occurrences:
            occurrences[base] += 1
            result = "{}-{}".format(base, occurrences[base])
        occurrences[result] = 0
        out.add(result)
    return out


def validate(text):
    errors, warnings = [], []
    lines = text.splitlines()

    # 1. frontmatter
    if not text.startswith("---"):
        errors.append("缺少 YAML frontmatter（首行应为 ---）")
    else:
        fm_end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        if fm_end is None:
            errors.append("frontmatter 未闭合（缺第二个 ---）")
        else:
            fm = "\n".join(lines[1:fm_end])
            for key in ("port:", "domain:", "updated:"):
                if key not in fm:
                    errors.append("frontmatter 缺 %s" % key.rstrip(":"))

    # 2. mojibake
    if "???" in text:
        errors.append("发现 ???（疑似编码损坏 / mojibake）")

    # 3. H1
    if not any(H1_RE.match(ln) for ln in lines):
        errors.append("缺少 `# <港口> 环境实例信息` 一级标题")

    # 4. section structure
    current_env = None
    seen_envs = []
    seen_h3 = {}
    instance_count = 0
    h3_open = None      # (lineno, heading) of the instance section being scanned
    h3_has_source = True

    def close_h3():
        if h3_open is not None and not h3_has_source:
            warnings.append("第%d行 实例节「%s」缺 `> 来源：…（日期）` 时效标记"
                            % (h3_open[0], h3_open[1]))

    for idx, ln in enumerate(lines, 1):
        m2 = H2_RE.match(ln)
        m3 = H3_RE.match(ln)
        if m2:
            close_h3()
            h3_open = None
            title = m2.group(1).strip()
            if title in ENVS:
                current_env = title
                seen_envs.append(title)
            elif title.startswith("待确认"):
                current_env = None
            else:
                errors.append("第%d行 非法二级节「%s」：只允许 %s / 待确认…"
                              % (idx, title, " / ".join(ENVS)))
                current_env = None
        elif m3:
            close_h3()
            title = m3.group(1).strip()
            h3_open = (idx, title)
            h3_has_source = False
            instance_count += 1
            if title in seen_h3:
                errors.append("第%d行 实例标题与第%d行重复（锚点会漂移）：%s"
                              % (idx, seen_h3[title], title))
            else:
                seen_h3[title] = idx
            if current_env is None:
                errors.append("第%d行 实例节出现在环境节（test/Pre-release/prod）之外：%s"
                              % (idx, title))
            elif not title.startswith(current_env + " · "):
                errors.append("第%d行 实例标题须以「%s · 」为前缀（保证文件内锚点唯一）：%s"
                              % (idx, current_env, title))
        else:
            if h3_open is not None and SOURCE_RE.match(ln):
                h3_has_source = True
        cm = CRED_RE.search(ln)
        if cm:
            errors.append("第%d行 疑似凭据明文（%s…）——本文档只允许「凭据获取：<指针>」"
                          % (idx, cm.group(0)[:30]))
    close_h3()

    for env in ENVS:
        if env not in seen_envs:
            errors.append("缺少环境节 `## %s`（该港口没有此环境时正文写「无」，节不能省）" % env)

    return {"ok": len(errors) == 0, "errors": errors, "warnings": warnings,
            "envs": seen_envs, "instances": instance_count}


def check_refs(doc_path, text, wiki_base):
    """Verify every inbound `_env/<file>#anchor` link in the wiki resolves here."""
    errors, refs = [], 0
    anchors = heading_slugs(text)
    fname = os.path.basename(doc_path)
    link_re = re.compile(r"\]\(([^)]*_env/%s)#([^)]+)\)" % re.escape(fname))
    skip_dirs = {".git", ".idea", ".obsidian", ".claude", ".claudian", "__pycache__"}
    for root, dirs, files in os.walk(wiki_base):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for f in files:
            if not f.endswith(".md"):
                continue
            p = os.path.join(root, f)
            if os.path.abspath(p) == os.path.abspath(doc_path):
                continue
            try:
                with io.open(p, "r", encoding="utf-8") as fh:
                    src = fh.read()
            except Exception:
                continue
            for m in link_re.finditer(src):
                refs += 1
                if m.group(2) not in anchors:
                    errors.append("断锚：%s 引用 %s#%s，本文档无此标题锚点"
                                  % (os.path.relpath(p, wiki_base), fname, m.group(2)))
    return {"ok": len(errors) == 0, "errors": errors, "inbound_refs": refs}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(json.dumps({"ok": False, "errors": ["usage: validate_env.py <path> [--check-refs] [--wiki-base <dir>]"],
                          "warnings": []}, ensure_ascii=False))
        return 2
    path = args[0]
    try:
        with io.open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"ok": False, "errors": ["无法读取：%s" % e], "warnings": []},
                         ensure_ascii=False))
        return 2

    result = validate(text)

    if "--check-refs" in sys.argv:
        wiki_base = None
        if "--wiki-base" in sys.argv:
            i = sys.argv.index("--wiki-base")
            if i + 1 < len(sys.argv):
                wiki_base = sys.argv[i + 1]
        if wiki_base is None:
            # <wiki>/<域>/_env/<port>.md → wiki root is 3 dirname hops up
            wiki_base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(path))))
        ref_result = check_refs(path, text, wiki_base)
        result["refs"] = ref_result
        result["ok"] = result["ok"] and ref_result["ok"]
        result["errors"] = result["errors"] + ref_result["errors"]

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())
