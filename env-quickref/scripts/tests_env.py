#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for validate_env.py — run: python -X utf8 tests_env.py (prints PASS/FAIL)."""
import validate_env as v

GOOD = """---
port: nb
domain: old_project
title: nb（梅山）环境实例信息
updated: 2026-07-14
---

# nb（梅山）环境实例信息

## test

### test · MySQL 主库

- 位置：待补
- 凭据获取：Mcp/np/test/ports.toml（指针）

> 来源：用户口述（2026-07-14）

## Pre-release

无

## prod

### prod · MySQL 主库

- 位置：待补

> 来源：用户口述（2026-07-14）

## 待确认 / 疑问

- [test · MySQL 主库] host:port 待口述（已检查 fms-log SKILL.md 未记载；建议核实方向：问运维）
"""

CASES = []


def case(name, mutate, expect_ok, expect_fragment=None):
    CASES.append((name, mutate, expect_ok, expect_fragment))


case("valid doc passes", lambda t: t, True)
case("missing frontmatter key", lambda t: t.replace("domain: old_project\n", ""), False, "domain")
case("illegal H2", lambda t: t.replace("## Pre-release", "## uat"), False, "非法二级节")
case("missing env section", lambda t: t.replace("## Pre-release\n\n无\n", ""), False, "缺少环境节")
case("instance without env prefix", lambda t: t.replace("### test · MySQL 主库", "### MySQL 主库"), False, "前缀")
case("wrong env prefix", lambda t: t.replace("### prod · MySQL 主库", "### test · MySQL 主库 prod 版"), False, "前缀")
case("duplicate instance heading", lambda t: t.replace("### prod · MySQL 主库", "### test · MySQL 主库"), False, "重复"),
case("credential plaintext =", lambda t: t.replace("位置：待补\n- 凭据获取", "位置：待补\n- password=hunter2\n- 凭据获取"), False, "凭据")
case("credential plaintext 密码：", lambda t: t.replace("- 位置：待补\n", "- 密码：s3cret\n", 1), False, "凭据")
case("pointer mentioning 密码在 is fine", lambda t: t.replace("（指针）", "（密码在该 toml，agent 不读值）"), True)
case("mojibake", lambda t: t.replace("待补", "??? 待补", 1), False, "???")
case("missing 来源 is warning only", lambda t: t.replace("> 来源：用户口述（2026-07-14）\n\n## Pre-release", "\n## Pre-release"), True)


def run():
    failed = 0
    for name, mutate, expect_ok, frag in CASES:
        r = v.validate(mutate(GOOD))
        ok = r["ok"] == expect_ok
        if ok and frag and expect_ok is False:
            ok = any(frag in e for e in r["errors"])
        print("%s %s" % ("PASS" if ok else "FAIL", name))
        if not ok:
            failed += 1
            print("      got ok=%s errors=%s" % (r["ok"], r["errors"]))
    # slug sanity (golden case from wiki_engine slug.py docstring)
    s = v.slug("6.6 OTA / 版本 / 文件日志流")
    ok = s == "66-ota--版本--文件日志流"
    print("%s slug golden case" % ("PASS" if ok else "FAIL"))
    if not ok:
        failed += 1
        print("      got %s" % s)
    print("%d failed" % failed)
    return 1 if failed else 0


if __name__ == "__main__":
    import sys
    sys.exit(run())
