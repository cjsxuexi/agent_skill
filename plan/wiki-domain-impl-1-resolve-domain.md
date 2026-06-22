# 域分层实现计划 1 / 5 — 引擎 `resolve-domain` + `.wiki.json`

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 `wiki_engine` 加一个确定性的 `resolve-domain` 子命令和 `.wiki.json` 注册表读写层，把"源码仓 → 域"的解析从 skill prose 下沉到引擎（设计 §5.2 / D9）。

**Architecture:** 新增 `wiki_engine/registry.py` 承载 `.wiki.json` 的读 / 解析 / 持久化（纯路径数学 + UTF-8 原子写）。`resolve()` 是唯一入口：命中 `repos` 映射或父目录在白名单 → 返回域；父目录不在白名单 → 抛 `UnknownDomain`（新增退出码 10），由调用方（skill）转成"指派/新建域"询问。`cli.py` 加一个薄包装子命令。域是强制项——没有 flat 分支。

**Tech Stack:** Python 3.8+ 标准库（`json` / `os` / `tempfile`）；`unittest`；引擎现有 `io_utf8`（强制 UTF-8、无 BOM、`os.replace` 原子写）与 `errors`（`EngineError` 体系 + 退出码）。

## Global Constraints

- **仅标准库**：引擎不引第三方依赖（Python 3.8+ stdlib）。
- **UTF-8 / 无 BOM / 原子写**：所有文件读写走 `io_utf8.read_text* / write_text`，绝不手写 `open(...).write` 写产物文件（测试夹具除外）。
- **引擎错误双语**：每个错误对象带英文 `code` + 中文 `message_zh`；CLI 每次调用**只打印一个 JSON 对象**到 stdout，退出码按 `errors.py`。
- **域强制、无 flat**：`.wiki.json` 的 `domains` 恒非空；`repos` 只存真实仓→域指派，不存 `null`。
- **不破坏既有引擎**：完成判据是 `python -X utf8 -m unittest discover scripts/wiki_engine/tests`（cwd = `D:\jk_file\skills\document-systems`）**全绿**，既有用例一个不挂。
- **命令工作目录**：本计划所有 `python` 命令的 cwd 均为 `D:\jk_file\skills\document-systems`。Windows 上用 `python`（非 `python3`）。

---

## File Structure

- `scripts/wiki_engine/registry.py` —（新建）`.wiki.json` 读/解析/写 + `resolve()`。单一职责：域注册表。
- `scripts/wiki_engine/errors.py` —（改）加退出码 `EXIT_NEED_DOMAIN = 10` 与 `UnknownDomain` 异常类。
- `scripts/wiki_engine/cli.py` —（改）加 `cmd_resolve_domain` + `resolve-domain` 子解析器；docstring 退出码表补 10。
- `scripts/wiki_engine/tests/test_registry.py` —（新建）`registry.py` 的单元测试（直接 import）。
- `scripts/wiki_engine/tests/test_cli.py` —（改）加 `resolve-domain` 的 CLI 级子进程测试。

---

## Task 1: 退出码 + `UnknownDomain` 错误类

**Files:**
- Modify: `scripts/wiki_engine/errors.py`
- Test: `scripts/wiki_engine/tests/test_registry.py`（本任务先建文件，仅放错误类测试）

**Interfaces:**
- Produces: `errors.EXIT_NEED_DOMAIN = 10`；`errors.UnknownDomain`（`code="E_UNKNOWN_DOMAIN"`、`exit_code=10`，继承 `EngineError`，构造签名同基类 `(message_zh, code=None, exit_code=None, detail=None)`）。

- [ ] **Step 1: 写失败测试**

新建 `scripts/wiki_engine/tests/test_registry.py`：

```python
"""Domain registry unit tests (域分层设计 §5.2)."""
import json
import os
import shutil
import tempfile
import unittest

import _support  # noqa: F401  (puts scripts/ on sys.path)
from wiki_engine import errors


class ErrorsTest(unittest.TestCase):
    def test_unknown_domain_shape(self):
        self.assertEqual(errors.EXIT_NEED_DOMAIN, 10)
        e = errors.UnknownDomain("父目录不在白名单", detail={"candidate": "experiments"})
        self.assertEqual(e.code, "E_UNKNOWN_DOMAIN")
        self.assertEqual(e.exit_code, 10)
        self.assertEqual(e.to_dict()["detail"]["candidate"], "experiments")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -X utf8 scripts/wiki_engine/tests/test_registry.py -v`
Expected: FAIL — `AttributeError: module 'wiki_engine.errors' has no attribute 'EXIT_NEED_DOMAIN'`。

- [ ] **Step 3: 实现**

在 `scripts/wiki_engine/errors.py` 的退出码常量块（`EXIT_NO_SOURCE = 9` 之后）加：

```python
EXIT_NEED_DOMAIN = 10
```

并把模块顶部 docstring 的退出码清单补一行（在 `9  source root missing ...` 之后）：

```
    10 domain resolution needs user input (E_UNKNOWN_DOMAIN)
```

在文件末尾（`RootEdgeDangling` 类之后）加异常类：

```python
class UnknownDomain(EngineError):
    code = "E_UNKNOWN_DOMAIN"
    exit_code = EXIT_NEED_DOMAIN
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -X utf8 scripts/wiki_engine/tests/test_registry.py -v`
Expected: PASS（`test_unknown_domain_shape`）。

- [ ] **Step 5: 提交**

```bash
git -C D:/jk_file/skills add document-systems/scripts/wiki_engine/errors.py document-systems/scripts/wiki_engine/tests/test_registry.py
git -C D:/jk_file/skills commit -m "feat(engine): add EXIT_NEED_DOMAIN + UnknownDomain error"
```

---

## Task 2: `registry.py` — 读 / 写 / 路径数学

**Files:**
- Create: `scripts/wiki_engine/registry.py`
- Test: `scripts/wiki_engine/tests/test_registry.py`（追加）

**Interfaces:**
- Produces:
  - `registry.REGISTRY_NAME == ".wiki.json"`
  - `registry.registry_path(wiki_base) -> str`
  - `registry.load_registry(wiki_base) -> dict|None`（None=文件不存在；返回 dict 时保证含 `"domains"`/`"repos"` 键）
  - `registry.save_registry(wiki_base, data) -> None`（UTF-8、indent=2、尾换行、原子写）
  - `registry.repo_name(repo_root) -> str`（= `basename(normpath(repo_root))`）
  - `registry.parent_candidate(repo_root) -> str`（= `basename(dirname(normpath(repo_root)))`）

- [ ] **Step 1: 写失败测试**

在 `test_registry.py` 追加（放在 `ErrorsTest` 之后、`__main__` 之前）：

```python
from wiki_engine import registry


class RegistryIOTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.wiki = os.path.join(self.tmp, "wiki")
        os.makedirs(self.wiki)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _repo(self, *parts):
        # 合成的源码仓路径；只用到它的 basename/dirname
        return os.path.join(self.tmp, "code", *parts)

    def test_load_absent_returns_none(self):
        self.assertIsNone(registry.load_registry(self.wiki))

    def test_save_then_load_roundtrip(self):
        registry.save_registry(self.wiki,
                               {"domains": ["old_project"], "repos": {"a": "old_project"}})
        reg = registry.load_registry(self.wiki)
        self.assertEqual(reg["domains"], ["old_project"])
        self.assertEqual(reg["repos"], {"a": "old_project"})

    def test_load_fills_missing_keys(self):
        with open(os.path.join(self.wiki, ".wiki.json"), "w", encoding="utf-8") as fh:
            fh.write("{}")
        reg = registry.load_registry(self.wiki)
        self.assertEqual(reg["domains"], [])
        self.assertEqual(reg["repos"], {})

    def test_path_math(self):
        self.assertEqual(registry.repo_name(self._repo("old_project", "fabusurfer")),
                         "fabusurfer")
        self.assertEqual(registry.parent_candidate(self._repo("old_project", "fabusurfer")),
                         "old_project")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -X utf8 scripts/wiki_engine/tests/test_registry.py -v`
Expected: FAIL — `ImportError: cannot import name 'registry'`（模块还不存在）。

- [ ] **Step 3: 实现**

新建 `scripts/wiki_engine/registry.py`：

```python
"""Domain registry — read/resolve/persist `.wiki.json` (域分层设计 §5.2).

`.wiki.json` lives at the wiki base (the single known location, avoiding the
`<DOC_ROOT>` chicken-and-egg) and holds:
  domains  authoritative whitelist of domain names (always >= 1; no flat mode)
  repos    map REPO_NAME -> domain (real assignments only; never null)
"""

import json
import os

from . import io_utf8
from .errors import UnknownDomain

REGISTRY_NAME = ".wiki.json"


def registry_path(wiki_base):
    return os.path.join(wiki_base, REGISTRY_NAME)


def load_registry(wiki_base):
    """Parsed `.wiki.json` (with `domains`/`repos` keys guaranteed), or None if absent."""
    raw = io_utf8.read_text_or_none(registry_path(wiki_base))
    if raw is None:
        return None
    data = json.loads(raw)
    data.setdefault("domains", [])
    data.setdefault("repos", {})
    return data


def save_registry(wiki_base, data):
    io_utf8.write_text(registry_path(wiki_base),
                       json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def repo_name(repo_root):
    return os.path.basename(os.path.normpath(repo_root))


def parent_candidate(repo_root):
    return os.path.basename(os.path.dirname(os.path.normpath(repo_root)))
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -X utf8 scripts/wiki_engine/tests/test_registry.py -v`
Expected: PASS（4 个 IO/路径用例 + Task 1 的错误用例）。

- [ ] **Step 5: 提交**

```bash
git -C D:/jk_file/skills add document-systems/scripts/wiki_engine/registry.py document-systems/scripts/wiki_engine/tests/test_registry.py
git -C D:/jk_file/skills commit -m "feat(engine): add registry.py (.wiki.json read/write + path helpers)"
```

---

## Task 3: `registry.resolve()` — 解析逻辑

**Files:**
- Modify: `scripts/wiki_engine/registry.py`
- Test: `scripts/wiki_engine/tests/test_registry.py`（追加）

**Interfaces:**
- Consumes: Task 2 的 `load_registry` / `save_registry` / `repo_name` / `parent_candidate`；Task 1 的 `UnknownDomain`。
- Produces: `registry.resolve(wiki_base, repo_root, set_domain=None) -> dict`：
  - `set_domain` 给定 → 持久化 `repos[REPO]=set_domain`（注册表不存在则新建；新域名追加进 `domains`），返回 `{"status":"resolved","repo","domain","source":"set"}`。
  - 无 `set_domain`：`{"status":"no_registry","repo","candidate"}`（无注册表）/ `{"status":"resolved","repo","domain","source":"repos"}`（映射命中）/ `{"status":"resolved","repo","domain","source":"parent"}`（父目录在白名单，**并写回 `repos`**）/ 抛 `UnknownDomain`（`detail={"repo","candidate","domains"}`）。

> 设计 §5.2 ③ 明确规定父目录命中时"输出并写回 `repos`"——这是 `resolve` 一个**有意的持久化副作用**（把推断结果固化，源码目录日后再动也不漂移）。`--set` 之外，仅 `source:"parent"` 这一支会写盘。

- [ ] **Step 1: 写失败测试**

在 `test_registry.py` 追加（`RegistryIOTest` 之后）：

```python
from wiki_engine.errors import UnknownDomain


class ResolveTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.wiki = os.path.join(self.tmp, "wiki")
        os.makedirs(self.wiki)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _repo(self, *parts):
        return os.path.join(self.tmp, "code", *parts)

    def _write(self, data):
        with open(os.path.join(self.wiki, ".wiki.json"), "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)

    def test_no_registry(self):
        res = registry.resolve(self.wiki, self._repo("old_project", "fabusurfer"))
        self.assertEqual(res["status"], "no_registry")
        self.assertEqual(res["candidate"], "old_project")

    def test_repos_hit(self):
        self._write({"domains": ["fms"], "repos": {"fabusurfer": "old_project"}})
        res = registry.resolve(self.wiki, self._repo("anything", "fabusurfer"))
        self.assertEqual(res, {"status": "resolved", "repo": "fabusurfer",
                               "domain": "old_project", "source": "repos"})

    def test_parent_resolves_and_persists(self):
        self._write({"domains": ["old_project"], "repos": {}})
        res = registry.resolve(self.wiki, self._repo("old_project", "fabusurfer"))
        self.assertEqual(res["domain"], "old_project")
        self.assertEqual(res["source"], "parent")
        self.assertEqual(registry.load_registry(self.wiki)["repos"]["fabusurfer"],
                         "old_project")  # 写回

    def test_unknown_raises_with_detail(self):
        self._write({"domains": ["old_project"], "repos": {}})
        with self.assertRaises(UnknownDomain) as cm:
            registry.resolve(self.wiki, self._repo("experiments", "foo"))
        self.assertEqual(cm.exception.detail["candidate"], "experiments")
        self.assertEqual(cm.exception.detail["domains"], ["old_project"])

    def test_set_creates_registry_and_appends_domain(self):
        res = registry.resolve(self.wiki, self._repo("x", "newrepo"), set_domain="newdom")
        self.assertEqual(res["domain"], "newdom")
        reg = registry.load_registry(self.wiki)
        self.assertIn("newdom", reg["domains"])
        self.assertEqual(reg["repos"]["newrepo"], "newdom")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -X utf8 scripts/wiki_engine/tests/test_registry.py -v`
Expected: FAIL — `AttributeError: module 'wiki_engine.registry' has no attribute 'resolve'`。

- [ ] **Step 3: 实现**

在 `scripts/wiki_engine/registry.py` 末尾追加：

```python
def resolve(wiki_base, repo_root, set_domain=None):
    """Map REPO_ROOT to a domain (设计 §5.2). Domains are mandatory — an
    unresolvable repo raises UnknownDomain for the skill to prompt on."""
    name = repo_name(repo_root)
    reg = load_registry(wiki_base)

    if set_domain is not None:
        if reg is None:
            reg = {"domains": [], "repos": {}}
        if set_domain not in reg["domains"]:
            reg["domains"].append(set_domain)
        reg["repos"][name] = set_domain
        save_registry(wiki_base, reg)
        return {"status": "resolved", "repo": name, "domain": set_domain, "source": "set"}

    if reg is None:
        return {"status": "no_registry", "repo": name,
                "candidate": parent_candidate(repo_root)}
    if name in reg["repos"]:
        return {"status": "resolved", "repo": name,
                "domain": reg["repos"][name], "source": "repos"}
    cand = parent_candidate(repo_root)
    if cand in reg["domains"]:
        reg["repos"][name] = cand
        save_registry(wiki_base, reg)   # 写回（§5.2 ③）
        return {"status": "resolved", "repo": name, "domain": cand, "source": "parent"}
    raise UnknownDomain(
        "仓 `{}` 的父目录 `{}` 不在域白名单中，请指派已有域或新建域".format(name, cand),
        detail={"repo": name, "candidate": cand, "domains": list(reg["domains"])},
    )
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -X utf8 scripts/wiki_engine/tests/test_registry.py -v`
Expected: PASS（全部用例）。

- [ ] **Step 5: 提交**

```bash
git -C D:/jk_file/skills add document-systems/scripts/wiki_engine/registry.py document-systems/scripts/wiki_engine/tests/test_registry.py
git -C D:/jk_file/skills commit -m "feat(engine): registry.resolve() — domain resolution (no flat, unknown raises)"
```

---

## Task 4: `resolve-domain` CLI 子命令

**Files:**
- Modify: `scripts/wiki_engine/cli.py`
- Test: `scripts/wiki_engine/tests/test_cli.py`（追加）

**Interfaces:**
- Consumes: Task 3 的 `registry.resolve`；现有 `_emit` / `EXIT_OK` / `main()` 的 `except EngineError`（自动把 `UnknownDomain` 转成 `to_dict()` + 退出码 10）。
- Produces: 子命令 `resolve-domain --repo <REPO_ROOT> --wiki <WIKI_BASE> [--set <domain>]`：成功打印 resolve 结果 dict 并退出 0；`UnknownDomain` 时打印 `{code,message_zh,detail}` 并退出 10。

- [ ] **Step 1: 写失败测试**

在 `scripts/wiki_engine/tests/test_cli.py` 的 `CliTest` 类内追加三个方法：

```python
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
        self.assertEqual(reg["repos"]["fms-server"], "fms")
        self.assertIn("fms", reg["domains"])
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -X utf8 scripts/wiki_engine/tests/test_cli.py -v`
Expected: FAIL — `resolve-domain` 未注册，`_JsonArgumentParser.error` 走 exit 2，断言 `code==0/10` 失败。

- [ ] **Step 3: 实现**

在 `scripts/wiki_engine/cli.py` 加命令函数（放在 `cmd_rule_catalog` 之后、`# ===` 分隔线之前）：

```python
def cmd_resolve_domain(args):
    from wiki_engine import registry
    _emit(registry.resolve(args.wiki, args.repo, set_domain=args.set_domain))
    return EXIT_OK
```

在 `build_parser()` 里 `rc = sub.add_parser("rule-catalog")` 之后、`return p` 之前注册子解析器：

```python
    rd = sub.add_parser("resolve-domain")
    rd.add_argument("--repo", required=True)
    rd.add_argument("--wiki", required=True)
    rd.add_argument("--set", dest="set_domain", default=None)
    rd.set_defaults(func=cmd_resolve_domain)
```

并把 `cli.py` 顶部 docstring 第 4 行的退出码串 `... 8 io / 9 source.` 改为 `... 8 io / 9 source / 10 need-domain.`

- [ ] **Step 4: 跑测试确认通过**

Run: `python -X utf8 scripts/wiki_engine/tests/test_cli.py -v`
Expected: PASS（新 3 个 + 既有 CLI 用例）。

- [ ] **Step 5: 跑全套回归**

Run: `python -X utf8 -m unittest discover scripts/wiki_engine/tests`
Expected: OK（全绿，既有用例不受影响）。

- [ ] **Step 6: 提交**

```bash
git -C D:/jk_file/skills add document-systems/scripts/wiki_engine/cli.py document-systems/scripts/wiki_engine/tests/test_cli.py
git -C D:/jk_file/skills commit -m "feat(engine): add resolve-domain CLI subcommand (exit 10 on unknown domain)"
```

---

## Self-Review

**Spec coverage（对设计 §5.2）：** `.wiki.json`（domains+repos）读写 = Task 2；`resolve-domain` 无-`--set` 四分支（no_registry / repos / parent+写回 / unknown 报错）= Task 3；`--set` 持久化 + 新域追加 = Task 3；非零退出报错（退出码 10）= Task 1+4；CLI 子命令 = Task 4。skill 侧的询问编排（§5.2 步骤 1-5）**不在本计划**——它属于"计划 4：skill+契约"，本计划只交付引擎确定性部分。`--init-domains` flag 同属计划 4（其底座 `--set` 已在此就绪）。

**Placeholder scan：** 无 TBD / "适当处理" / 省略代码；每个代码步都给了完整可粘贴内容。

**Type consistency：** `resolve(wiki_base, repo_root, set_domain=None)` 返回的 dict 键（`status`/`repo`/`domain`/`source`/`candidate`）在 Task 3 定义、Task 4 测试按同名断言；`UnknownDomain.detail` 键（`repo`/`candidate`/`domains`）Task 1 构造、Task 3 抛出、Task 3+4 断言一致；退出码 `10` 在 errors / cli docstring / 测试三处一致。

**边界自查：** `resolve` 的 `source:"parent"` 分支写盘是设计 §5.2 ③ 钦定的副作用，已在 Interfaces 注明；其余分支只读。

---

## 后续计划（本计划完成后再逐一写）

- **计划 2**：三级 `_common`（`ops` 加 `level=domain` + 深度数学 + `lint/rules.py` 校验 + 测试）。
- **计划 3**：`update_domain_index`（薄域索引生成 + 测试）。
- **计划 4**：两个 SKILL.md Phase 1.0 接 `resolve-domain` + 询问编排 + `--init-domains`/`--domain-index` flag + 契约/模板 + MAINTAINER。
- **计划 5**：用改造后的 skill 跑 `D:\wiki` 存量迁移（即验证）。
