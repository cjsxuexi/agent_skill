# 域分层实现计划 3 / 5 — 域 `index.md` 生成器（+ 关闭 Plan 1 遗留）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给引擎加一个确定性的"域薄索引"生成器：扫 `<wiki_base>/<domain>/*/architecture.md`，生成一张只作导航、不复述内容的 `<wiki_base>/<domain>/index.md`（设计 §5.4 / D5）。顺带关闭 Plan 1 遗留：`load_registry` 对损坏 `.wiki.json` 抛 `ParseError`。

**Architecture:** 新增 `wiki_engine/domain_index.py`（纯扫描 + 渲染 + 原子写，类比 `registry.py`）：`build_index(wiki_base, domain)` 扫域目录下每个含 `architecture.md` 的仓子目录，取其 H1 标题 + 首个散文摘要行，渲染成一张薄表（仓 / 说明 / `./<repo>/architecture.md` 链接）+ 一段链到 `./_common/`；`write_index` 经 `io_utf8.write_text` 原子落盘。`cli.py` 加薄命令 `update-domain-index`。`index.md`（非 `.index.md`）不被派生文件 lint 命中，安全。

**Tech Stack:** Python 3.8+ 标准库；`unittest`；引擎现有 `parser`（取 H1/首行）、`io_utf8`（原子 UTF-8 写）、`errors`（`ParseError`/exit 7）。

## Global Constraints

- **薄索引、只导航**：域 `index.md` 每行 `仓名 / 一句话 / 链接 ./<repo>/architecture.md` + 一段链到 `./_common/`；**不复述内容、不读源码、不跨仓分析**（wiki-principles §7 / common-conventions §6 的派生索引 carve-out 扩到域级）。
- **只反映已生成文档的仓**：扫 `<domain>/<repo>/architecture.md` 存在者；忽略 `_`/`.` 前缀目录与无 `architecture.md` 的子目录。随仓增量增长。
- **机械、可重生、无漂移**：一句话＝该仓 `architecture.md` 的 H1 + 首个非空散文行（非标题/引用/表格/围栏）。重复生成幂等。
- **仅标准库；UTF-8/无 BOM/原子写**（`io_utf8.write_text`）；表格单元里的 `|` 转义为 `\|`。
- **不破坏既有引擎**：`python -X utf8 -m unittest discover scripts/wiki_engine/tests`（cwd=`D:\jk_file\skills\document-systems`）全绿。**凡改共享行为的任务，收尾跑全套**（Plan 2 教训：单测试文件 green-check 漏掉跨文件回归）。
- **命令工作目录** = `D:\jk_file\skills\document-systems`；Windows 用 `python -X utf8`。单文件测试 `python -X utf8 scripts/wiki_engine/tests/<file>.py -v`；提交走 `git -C D:/jk_file/skills`。

---

## File Structure

- `scripts/wiki_engine/domain_index.py` —（新建）扫描 + 渲染 + 写 域 `index.md`。
- `scripts/wiki_engine/tests/test_domain_index.py` —（新建）`domain_index` 单元测试。
- `scripts/wiki_engine/cli.py` —（改）加 `cmd_update_domain_index` + `update-domain-index` 子解析器。
- `scripts/wiki_engine/tests/test_cli.py` —（改）加 CLI 级测试。
- `scripts/wiki_engine/registry.py` —（改）`load_registry` 对损坏 JSON 抛 `ParseError`。
- `scripts/wiki_engine/tests/test_registry.py` —（改）加损坏-JSON 测试。

---

## Task 1: `domain_index.py` — 扫描 / 渲染 / 写

**Files:**
- Create: `scripts/wiki_engine/domain_index.py`
- Test: `scripts/wiki_engine/tests/test_domain_index.py`

**Interfaces:**
- Produces:
  - `domain_index.INDEX_NAME == "index.md"`
  - `domain_index.build_index(wiki_base, domain) -> str`（渲染好的 markdown 文本）
  - `domain_index.write_index(wiki_base, domain) -> str`（写盘并返回 abspath）
  - 内部：`_repo_dirs(domain_dir)`、`_summary(doc) -> (title, one_line)`、`_render(domain, rows)`

- [ ] **Step 1: 写失败测试**

新建 `scripts/wiki_engine/tests/test_domain_index.py`：

```python
"""Domain index generator unit tests (域分层设计 §5.4)."""
import os
import shutil
import tempfile
import unittest

import _support  # noqa: F401
from wiki_engine import domain_index


class DomainIndexTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.dom = os.path.join(self.tmp, "old_project")
        self._repo("fabusurfer", "# fabusurfer 系统总览\n\nfabusurfer 是港口云控核心。\n")
        self._repo("common-lib", "# common-lib\n\n共享库与 grpc-api 契约。\n")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _repo(self, name, arch_text):
        d = os.path.join(self.dom, name)
        os.makedirs(d)
        with open(os.path.join(d, "architecture.md"), "w", encoding="utf-8") as fh:
            fh.write(arch_text)

    def test_build_index_lists_repos(self):
        out = domain_index.build_index(self.tmp, "old_project")
        self.assertIn("# old_project 域索引", out)
        self.assertIn("[fabusurfer 系统总览](./fabusurfer/architecture.md)", out)
        self.assertIn("fabusurfer 是港口云控核心。", out)
        self.assertIn("[common-lib](./common-lib/architecture.md)", out)
        self.assertIn("共享库与 grpc-api 契约。", out)
        self.assertIn("./_common/", out)

    def test_build_index_skips_non_repos(self):
        os.makedirs(os.path.join(self.dom, "_common"))          # 下划线命名空间
        os.makedirs(os.path.join(self.dom, "notarepo"))         # 无 architecture.md
        out = domain_index.build_index(self.tmp, "old_project")
        self.assertNotIn("notarepo", out)
        self.assertNotIn("](./_common/architecture.md)", out)

    def test_summary_falls_back_to_repo_name(self):
        self._repo("nohead", "没有一级标题，直接正文一句。\n")
        out = domain_index.build_index(self.tmp, "old_project")
        # 无 H1 时标题回退为仓名，链接文本即仓名
        self.assertIn("[nohead](./nohead/architecture.md)", out)
        self.assertIn("没有一级标题，直接正文一句。", out)

    def test_pipe_escaped_in_cells(self):
        self._repo("pipey", "# A|B 标题\n\n含 | 竖线 的摘要。\n")
        out = domain_index.build_index(self.tmp, "old_project")
        self.assertIn("A\\|B 标题", out)
        self.assertIn("含 \\| 竖线 的摘要。", out)

    def test_write_index_creates_file(self):
        path = domain_index.write_index(self.tmp, "old_project")
        self.assertEqual(os.path.normpath(path),
                         os.path.normpath(os.path.join(self.dom, "index.md")))
        with open(path, encoding="utf-8") as fh:
            self.assertIn("old_project 域索引", fh.read())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -X utf8 scripts/wiki_engine/tests/test_domain_index.py -v`
Expected: FAIL — `ImportError: cannot import name 'domain_index'`（模块还不存在）。

- [ ] **Step 3: 实现**

新建 `scripts/wiki_engine/domain_index.py`：

```python
"""Domain index — generate the thin <wiki_base>/<domain>/index.md (design §5.4).

Navigation-only derived file: one row per documented repo (name / one-line / link)
plus a pointer to the domain `_common/`. Regenerated by scanning
`<wiki_base>/<domain>/*/architecture.md`; it never restates content. `index.md`
(not `.index.md`) is intentionally NOT matched by the derived-file lint.
"""

import os

from . import io_utf8, parser

INDEX_NAME = "index.md"


def _repo_dirs(domain_dir):
    """Subdirs of a domain dir that contain an `architecture.md` (sorted; skips _*/.* )."""
    out = []
    try:
        names = os.listdir(domain_dir)
    except OSError:
        return out
    for name in sorted(names):
        if name.startswith(".") or name.startswith("_"):
            continue
        if os.path.isfile(os.path.join(domain_dir, name, "architecture.md")):
            out.append(name)
    return out


def _summary(doc):
    """(H1 title or None, first plain-prose line or "") of an architecture.md doc."""
    h1 = next((h for h in doc.headings if h.level == 1), None)
    title = h1.text if h1 else None
    after = h1.line_end if h1 else doc.frontmatter.end
    one_line = ""
    for s, e in parser._line_spans(doc.text):
        if s < after:
            continue
        c = parser._line_content(doc.text, s, e).strip()
        if not c:
            continue
        if c[0] in "#>|" or c.startswith("```") or c.startswith("~~~"):
            continue
        one_line = c
        break
    return title, one_line


def _cell(s):
    return s.replace("|", "\\|")


def _render(domain, rows):
    """rows: list of (repo, title, one_line)."""
    lines = [
        "# {} 域索引".format(domain),
        "",
        "> 本页由引擎自动生成（域内各仓总览 + 域级公共文档导航），仅作导航、不复述内容。",
        "",
        "## 仓",
        "",
        "| 仓 | 说明 | 文档 |",
        "|---|---|---|",
    ]
    for repo, title, one_line in rows:
        link = "[{}](./{}/architecture.md)".format(_cell(title), repo)
        lines.append("| {} | {} | {} |".format(repo, _cell(one_line) or "—", link))
    lines += [
        "",
        "## 域级公共文档",
        "",
        "见 [`_common/`](./_common/)。",
        "",
    ]
    return "\n".join(lines) + "\n"


def build_index(wiki_base, domain):
    domain_dir = os.path.join(wiki_base, domain)
    rows = []
    for repo in _repo_dirs(domain_dir):
        arch = os.path.join(domain_dir, repo, "architecture.md")
        doc = parser.parse(arch, io_utf8.read_text(arch))
        title, one_line = _summary(doc)
        rows.append((repo, title or repo, one_line))
    return _render(domain, rows)


def write_index(wiki_base, domain):
    content = build_index(wiki_base, domain)
    path = os.path.normpath(os.path.join(wiki_base, domain, INDEX_NAME))
    io_utf8.write_text(path, content)
    return path
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -X utf8 scripts/wiki_engine/tests/test_domain_index.py -v`
Expected: PASS（5 个用例）。

- [ ] **Step 5: 提交**

```bash
git -C D:/jk_file/skills add document-systems/scripts/wiki_engine/domain_index.py document-systems/scripts/wiki_engine/tests/test_domain_index.py
git -C D:/jk_file/skills commit -m "feat(engine): domain_index.py — thin <domain>/index.md generator"
```

---

## Task 2: `update-domain-index` CLI 子命令

**Files:**
- Modify: `scripts/wiki_engine/cli.py`
- Test: `scripts/wiki_engine/tests/test_cli.py`

**Interfaces:**
- Consumes: Task 1 的 `domain_index.write_index`。
- Produces: `update-domain-index --wiki <WIKI_BASE> --domain <DOMAIN>` → 写 `<wiki>/<domain>/index.md`，打印 `{"status":"ok","domain","index","message_zh"}`，退出 0。

- [ ] **Step 1: 写失败测试**

在 `scripts/wiki_engine/tests/test_cli.py` 的 `CliTest` 类内追加：

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -X utf8 scripts/wiki_engine/tests/test_cli.py -v`
Expected: FAIL — `update-domain-index` 未注册 → `_JsonArgumentParser.error` 走 exit 2，`code==0` 断言失败。

- [ ] **Step 3: 实现**

在 `scripts/wiki_engine/cli.py` 加命令函数（放在 `cmd_rule_catalog` 之后、`# ===...` 分隔线之前）：

```python
def cmd_update_domain_index(args):
    from wiki_engine import domain_index
    path = domain_index.write_index(args.wiki, args.domain)
    _emit({"status": "ok", "domain": args.domain, "index": path,
           "message_zh": "已生成域索引：{}".format(path)})
    return EXIT_OK
```

在 `build_parser()` 里 `rc = sub.add_parser("rule-catalog")` 那段之后、`return p` 之前注册子解析器：

```python
    udi = sub.add_parser("update-domain-index")
    udi.add_argument("--wiki", required=True)
    udi.add_argument("--domain", required=True)
    udi.set_defaults(func=cmd_update_domain_index)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -X utf8 scripts/wiki_engine/tests/test_cli.py -v`
Expected: PASS（新测试 + 既有 CLI 测试）。

- [ ] **Step 5: 提交**

```bash
git -C D:/jk_file/skills add document-systems/scripts/wiki_engine/cli.py document-systems/scripts/wiki_engine/tests/test_cli.py
git -C D:/jk_file/skills commit -m "feat(engine): add update-domain-index CLI subcommand"
```

---

## Task 3: `load_registry` 损坏 JSON → `ParseError`（关闭 Plan 1 遗留）

**Files:**
- Modify: `scripts/wiki_engine/registry.py`
- Test: `scripts/wiki_engine/tests/test_registry.py`

**Interfaces:**
- Produces: `load_registry(wiki_base)` 遇到非法 JSON 的 `.wiki.json` 时抛 `errors.ParseError`（`code="E_PARSE"`，exit 7），而非裸 `json.JSONDecodeError`。

> 来由：Plan 1 final review 指出 `.wiki.json` 是新单点，损坏时应抛引擎类型化错误。Plan 4 的 skill 会大量调 `resolve-domain`/`load_registry`，提前在引擎兜住。

- [ ] **Step 1: 写失败测试**

在 `scripts/wiki_engine/tests/test_registry.py` 的 `RegistryIOTest` 类内追加：

```python
    def test_load_malformed_json_raises_parse_error(self):
        from wiki_engine.errors import ParseError
        with open(os.path.join(self.wiki, ".wiki.json"), "w", encoding="utf-8") as fh:
            fh.write("{ this is not json ")
        with self.assertRaises(ParseError) as cm:
            registry.load_registry(self.wiki)
        self.assertEqual(cm.exception.exit_code, 7)
        self.assertEqual(cm.exception.code, "E_PARSE")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -X utf8 scripts/wiki_engine/tests/test_registry.py -v`
Expected: FAIL — 当前 `load_registry` 直接 `json.loads` → 抛 `json.JSONDecodeError`（非 `ParseError`），`assertRaises(ParseError)` 失败。

- [ ] **Step 3: 实现**

在 `scripts/wiki_engine/registry.py`：

把导入行（约 line 13）
```python
from .errors import UnknownDomain
```
改为
```python
from .errors import UnknownDomain, ParseError
```
（`registry.py` 顶部已有 `import json`，json 导入无需改动。）

把 `load_registry` 里
```python
    data = json.loads(raw)
```
改为
```python
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ParseError("`.wiki.json` 不是合法 JSON：{}".format(exc),
                         detail={"path": registry_path(wiki_base)})
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -X utf8 scripts/wiki_engine/tests/test_registry.py -v`
Expected: PASS（含新损坏-JSON 用例）。

- [ ] **Step 5: 跑全套回归**

Run: `python -X utf8 -m unittest discover scripts/wiki_engine/tests`
Expected: OK（全绿）。

- [ ] **Step 6: 提交**

```bash
git -C D:/jk_file/skills add document-systems/scripts/wiki_engine/registry.py document-systems/scripts/wiki_engine/tests/test_registry.py
git -C D:/jk_file/skills commit -m "fix(engine): load_registry raises ParseError on malformed .wiki.json (exit 7)"
```

---

## Self-Review

**Spec coverage（设计 §5.4 / D5）：** 薄域索引（仓名/一句话/链接 + `_common` 导航）= Task 1 的 `_render`；扫"已生成文档的仓"、忽略 `_`/`.`、无 `architecture.md` 不计 = `_repo_dirs`；一句话＝H1+首散文行、机械可重生 = `_summary`；CLI 触发 = Task 2（自动刷新触发器属 skill，Plan 4）。Plan 1 遗留 `ParseError` = Task 3。**不在本计划**：`/document-systems` 跑完自动刷域 index（skill 编排，Plan 4）；根文档对 domain/global `_common` 链接（Plan 4）。

**Placeholder scan：** 无 TBD / 省略；每步给完整代码。

**Type consistency：** `build_index/write_index(wiki_base, domain)` 签名贯穿 Task 1/2；`_summary` 返回 `(title, one_line)`，`build_index` 用 `title or repo` 兜空；CLI 返回键 `status/domain/index/message_zh` 与测试断言一致；`ParseError`（exit 7）跨 errors/registry/test 一致。

**Lint 自查：** 域 `index.md` 为 ANCILLARY（light），其文件级 `./<repo>/architecture.md` 链接是导航惯例；`index.md`（非 `.index.md`）不被 `DERIVED_RE` 命中；`[`_common/`](./_common/)` 非 `.md` 链接、不触发链接目标/锚点规则。

**回归自查：** Task 1/2 纯新增（新模块 + 新命令），不动既有行为；Task 3 改 `load_registry` 仅在"文件存在但非法 JSON"路径插 try/except，正常路径不变；Task 3 收尾跑全套（含 registry/resolve-domain 既有用例）。

---

## 后续计划

- **计划 4**：两个 SKILL.md Phase 1.0 接 `resolve-domain` + 询问编排 + `--init-domains`/`--domain-index`（跑完自动刷域 index）；根文档 `仓内公共文档` 对 domain/global `_common` 链接；`common-conventions`/`root-architecture` 模板/MAINTAINER 同步；`init-common` 统一入参校验（Plan 2 遗留）。
- **计划 5**：用改造后的 skill 跑 `D:\wiki` 存量迁移（即验证）。
