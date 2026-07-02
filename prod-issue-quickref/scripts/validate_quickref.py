#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only validator for a 生产问题速查.md diagnostic-tree doc.

Exit 0 = OK (may carry warnings); exit 2 = hard fail. Prints a JSON summary to stdout.
Hard fails (block an auto-write): unreadable file, missing frontmatter/title,
`???` mojibake, or a `根因` leaf without a `](....md)` confirm link.
Style issues (banned inline content, 判别 without 根因) are warnings only.

Usage: python -X utf8 validate_quickref.py <path-to-生产问题速查.md>
"""
import sys
import io
import json
import re

LINK_RE = re.compile(r"\]\((\.{0,2}/?[^)]*\.md[^)]*)\)")
GENYIN_RE = re.compile(r"^\s*-\s*\*\*根因\*\*")
PANBIE_RE = re.compile(r"^\s*-\s*\*\*判别\*\*")
BANNED = ["恢复 / 缓解方向", "恢复/缓解方向", "## 待确认", "## 恢复", "待确认列表"]


def validate(text):
    errors, warnings = [], []
    lines = text.splitlines()

    # 1. frontmatter with a title
    if not text.startswith("---"):
        errors.append("缺少 YAML frontmatter（首行应为 ---）")
    else:
        fm_end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        if fm_end is None:
            errors.append("frontmatter 未闭合（缺第二个 ---）")
        elif "title:" not in "\n".join(lines[1:fm_end]):
            errors.append("frontmatter 缺 title")

    # 2. mojibake
    if "???" in text:
        errors.append("发现 ???（疑似编码损坏 / mojibake）")

    # 3. tree shape + leaf-link rule
    roots = [ln for ln in lines if ln.startswith("## ")]
    if not roots:
        warnings.append("没有任何 `## 现象` 根节点（空树 / 刚 init 属正常）")

    saw_panbie = False
    for idx, ln in enumerate(lines, 1):
        if PANBIE_RE.match(ln):
            saw_panbie = True
        if GENYIN_RE.match(ln) or "**根因**" in ln:
            if not LINK_RE.search(ln):
                errors.append("第%d行 根因叶子缺少 `](....md)` 确认链接：%s"
                              % (idx, ln.strip()[:70]))
        for b in BANNED:
            if b in ln:
                warnings.append("第%d行 含疑似被禁内容『%s』（应放进被链接的 wiki 文档，不写树里）"
                                % (idx, b))
    if roots and not saw_panbie:
        warnings.append("有现象根但没有任何 `- **判别**` 分支")

    return {"ok": len(errors) == 0, "errors": errors,
            "warnings": warnings, "roots": len(roots)}


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"ok": False, "errors": ["usage: validate_quickref.py <path>"],
                          "warnings": [], "roots": 0}, ensure_ascii=False))
        return 2
    try:
        with io.open(sys.argv[1], "r", encoding="utf-8") as f:
            text = f.read()
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"ok": False, "errors": ["无法读取：%s" % e],
                          "warnings": [], "roots": 0}, ensure_ascii=False))
        return 2
    result = validate(text)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())
