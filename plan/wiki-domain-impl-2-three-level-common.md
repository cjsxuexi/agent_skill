# 域分层实现计划 2 / 5 — 三级 `_common`（domain 级）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把引擎现有的两级 `_common`（repo / global）扩成三级（repo / **domain** / global），使 `promote_to_common` 与 `init-common` 支持 `level=domain`，并修正 global 的路径深度（域层把它顶深一级）。

**Architecture:** `doc_root` 在 Plan 1 之后恒为 `<wiki_base>/<domain>/<repo>`。`_common` 的三处位置全部由 `_common_target_path` 从 `doc_root` 经 `dirname` 推出：repo=`doc_root/_common`、domain=`dirname(doc_root)/_common`、global=`dirname(dirname(doc_root))/_common`。链接深度（从根文档看：`./_common/` / `../_common/` / `../../_common/`）由这同一函数给出；引用方链接深度由调用方负责，**错误深度由现有 `LINK_TARGET_EXISTS` lint 自动拦截**（链接解析到不存在的文件即报错），故本计划**不新增深度 lint 规则**。

**Tech Stack:** Python 3.8+ 标准库；`unittest`；引擎现有 `ops`（算子）、`lint`（规则）、`cli`（子命令）。

## Global Constraints

- **域恒在、doc_root 三段式**：`doc_root = <wiki_base>/<domain>/<repo>`（Plan 1 已强制域、无 flat）。所有 `_common` 路径据此经 `dirname` 推算。
- **三级深度（从仓根文档看）**：repo `./_common/`、domain `../_common/`、global `../../_common/`。这是 §4.3 设计表，必须与 `_common_target_path` 的 `rel_display` 一致。
- **不新增深度 lint**：错误的 `../` 深度＝链接指向不存在文件＝现有 `LINK_TARGET_EXISTS`（ERROR）自动拦截。本计划只把 `level` 枚举从 `repo/global` 扩到 `repo/domain/global`。
- **仅标准库；UTF-8/无 BOM/原子写**（`io_utf8`）；引擎错误带英文 `code`+中文 `message_zh`；CLI 每次一个 JSON。
- **不破坏既有引擎**：完成判据 `python -X utf8 -m unittest discover scripts/wiki_engine/tests`（cwd=`D:\jk_file\skills\document-systems`）全绿；既有 `_common` 测试中**对 global 的旧二级假设需随之更新到三级**（见 Task 2）。
- **命令工作目录** = `D:\jk_file\skills\document-systems`；Windows 用 `python -X utf8`（非 python3）。单测试文件可直接 `python -X utf8 scripts/wiki_engine/tests/<file>.py -v`；提交走 `git -C D:/jk_file/skills`。

---

## File Structure

- `scripts/wiki_engine/lint/rules.py` —（改）`COMMON_LEVELS` 加 `"domain"`；`check_common_frontmatter` 错误文案。
- `scripts/wiki_engine/tests/test_lint.py` —（改）`test_common_frontmatter_valid_and_invalid` 增 domain-合法断言。
- `scripts/wiki_engine/ops/__init__.py` —（改）`_common_target_path` 三级；`op_promote_to_common` 的 `level_zh` 映射。
- `scripts/wiki_engine/tests/test_ops.py` —（改）旧 global 测试重定义为 domain；新增 global 三级测试。
- `scripts/wiki_engine/cli.py` —（改）`cmd_init_common` 支持 domain + 修正 global 三级；`init-common` 子解析器加 `domain` 选项与 `--domain`。
- `scripts/wiki_engine/tests/test_cli.py` —（改）新增 `init-common --level domain` 测试。

---

## Task 1: lint 接受 `level: domain`

**Files:**
- Modify: `scripts/wiki_engine/lint/rules.py`
- Test: `scripts/wiki_engine/tests/test_lint.py`

**Interfaces:**
- Produces: `COMMON_LEVELS == {"repo", "domain", "global"}`；`COMMON_FRONTMATTER` 不再对 `level: domain` 报错。

- [ ] **Step 1: 写失败测试**

在 `scripts/wiki_engine/tests/test_lint.py` 的 `test_common_frontmatter_valid_and_invalid` 方法末尾（line 117 的 `self.assertIn("COMMON_FRONTMATTER", ...)` 之后）追加：

```python
        # domain 级别合法（三级 common）
        domain_doc = ("---\ncommon_type: glossary\nlevel: domain\nowns: x\n---\n"
                      "# x\n\n## 1. 范围与级别\n\n无\n\n## 待确认 / 疑问\n\n无\n")
        ctx2 = _ctx(None, DocKind.COMMON, rel="_common/x.md", text=domain_doc)
        self.assertNotIn("COMMON_FRONTMATTER", _ids(lint.run_lint(ctx2)))
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -X utf8 scripts/wiki_engine/tests/test_lint.py -v`
Expected: FAIL — `test_common_frontmatter_valid_and_invalid` 失败：`level: domain` 当前被判非法 → `COMMON_FRONTMATTER` 出现在结果里，`assertNotIn` 失败。

- [ ] **Step 3: 实现**

在 `scripts/wiki_engine/lint/rules.py`：

把（line 26）
```python
COMMON_LEVELS = {"repo", "global"}
```
改为
```python
COMMON_LEVELS = {"repo", "domain", "global"}
```

把 `check_common_frontmatter` 里（约 line 377-379）
```python
    if lv not in COMMON_LEVELS:
        out.append(ctx.make(R_COMMON_FM, ERROR,
                            "level 非法或缺失：{}（须为 repo/global）".format(lv), "frontmatter"))
```
改为
```python
    if lv not in COMMON_LEVELS:
        out.append(ctx.make(R_COMMON_FM, ERROR,
                            "level 非法或缺失：{}（须为 repo/domain/global）".format(lv), "frontmatter"))
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -X utf8 scripts/wiki_engine/tests/test_lint.py -v`
Expected: PASS（含更新后的 `test_common_frontmatter_valid_and_invalid`）。

- [ ] **Step 5: 提交**

```bash
git -C D:/jk_file/skills add document-systems/scripts/wiki_engine/lint/rules.py document-systems/scripts/wiki_engine/tests/test_lint.py
git -C D:/jk_file/skills commit -m "feat(engine): lint accepts common level=domain (three-level common)"
```

---

## Task 2: `_common_target_path` 三级 + promote `level_zh`

**Files:**
- Modify: `scripts/wiki_engine/ops/__init__.py`
- Test: `scripts/wiki_engine/tests/test_ops.py`

**Interfaces:**
- Produces: `_common_target_path(txn, level, common_name)` 支持 `level ∈ {repo, domain, global}`：
  - repo → `<doc_root>/_common/<n>.md`，`rel_display="_common/<n>.md"`
  - domain → `dirname(doc_root)/_common/<n>.md`，`rel_display="../_common/<n>.md"`
  - global → `dirname(dirname(doc_root))/_common/<n>.md`，`rel_display="../../_common/<n>.md"`
- `op_promote_to_common` 的 scope 句对 domain 显示「域级」。
- Consumes: Plan 1 的 `doc_root` 三段式约定。

> 注意 backward-compat：global 的语义从「`dirname(doc_root)`」变为「`dirname(dirname(doc_root))`」——这是域层把 global 顶深一级的必然结果。旧的 `test_promote_to_common_global_path`（断言 `dirname(doc_root)` + `../_common/`）在三级模型下**正好是 domain 的语义**，故将其重定义为 domain 测试，并新增真正的 global 测试。

- [ ] **Step 1: 写失败测试**

在 `scripts/wiki_engine/tests/test_ops.py` 中，把现有 `test_promote_to_common_global_path`（约 line 229-242）**整体替换**为下面两个方法：

```python
    def test_promote_to_common_domain_path(self):
        tf = self._payload("t.md", "域级术语")
        bf = self._payload("b.md", "| `x` | y | z |")
        op = {"op": "promote_to_common", "level": "domain", "type": "glossary",
              "common_name": "domain-terms", "title_file": tf, "body_file": bf,
              "sources": []}
        res = ops.op_promote_to_common(self.txn, op, 0)
        abspath, rel_display, content = res.new_files[0]
        # domain -> dirname(doc_root)/_common
        domain_dir = os.path.dirname(os.path.normpath(self.tmp))
        self.assertEqual(os.path.normpath(abspath),
                         os.path.normpath(os.path.join(domain_dir, "_common", "domain-terms.md")))
        self.assertEqual(rel_display, "../_common/domain-terms.md")
        self.assertIn("level: domain", content)

    def test_promote_to_common_global_path(self):
        tf = self._payload("t.md", "全局术语")
        bf = self._payload("b.md", "| `x` | y | z |")
        op = {"op": "promote_to_common", "level": "global", "type": "glossary",
              "common_name": "global-terms", "title_file": tf, "body_file": bf,
              "sources": []}
        res = ops.op_promote_to_common(self.txn, op, 0)
        abspath, rel_display, content = res.new_files[0]
        # global -> dirname(dirname(doc_root))/_common  (域层把 global 顶深一级)
        wiki_base = os.path.dirname(os.path.dirname(os.path.normpath(self.tmp)))
        self.assertEqual(os.path.normpath(abspath),
                         os.path.normpath(os.path.join(wiki_base, "_common", "global-terms.md")))
        self.assertEqual(rel_display, "../../_common/global-terms.md")
        self.assertIn("level: global", content)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -X utf8 scripts/wiki_engine/tests/test_ops.py -v`
Expected: FAIL — `test_promote_to_common_global_path` 失败（旧实现 global 仍解析为 `dirname(doc_root)`，rel `../_common/`，与新断言 `../../_common/` 不符）；`test_promote_to_common_domain_path` 也失败（`level=domain` 落到 else 分支＝repo 路径 `_common/`，rel 不为 `../_common/`）。

- [ ] **Step 3: 实现**

在 `scripts/wiki_engine/ops/__init__.py`：

把 `_common_target_path`（约 line 234-245）整体替换为：
```python
def _common_target_path(txn, level, common_name):
    """Three-level common (doc_root = <wiki_base>/<domain>/<repo>):
      repo   -> <doc_root>/_common/<name>.md            (rel ./_common/  from root doc)
      domain -> <wiki_base>/<domain>/_common/<name>.md  (rel ../_common/  from root doc)
      global -> <wiki_base>/_common/<name>.md           (rel ../../_common/ from root doc)
    Returns (abspath, rel_display)."""
    fname = "{}.md".format(common_name)
    doc_root = os.path.normpath(txn.doc_root)
    if level == "global":
        base = os.path.dirname(os.path.dirname(doc_root))
        rel_display = "../../_common/{}".format(fname)
    elif level == "domain":
        base = os.path.dirname(doc_root)
        rel_display = "../_common/{}".format(fname)
    else:  # repo
        base = doc_root
        rel_display = "_common/{}".format(fname)
    abspath = os.path.normpath(os.path.join(base, "_common", fname))
    return abspath, rel_display
```

把 `op_promote_to_common` 里（约 line 211）
```python
    level_zh = "仓库级" if level == "repo" else "全局"
```
改为
```python
    level_zh = {"repo": "仓库级", "domain": "域级", "global": "全局"}.get(level, level)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -X utf8 scripts/wiki_engine/tests/test_ops.py -v`
Expected: PASS（含新的 domain + global 两个 promote 测试；`test_promote_to_common_scaffolds_and_rewrites` 的 repo 路径不变仍过）。

- [ ] **Step 5: 提交**

```bash
git -C D:/jk_file/skills add document-systems/scripts/wiki_engine/ops/__init__.py document-systems/scripts/wiki_engine/tests/test_ops.py
git -C D:/jk_file/skills commit -m "feat(engine): three-level _common path (repo/domain/global) + domain level_zh"
```

---

## Task 3: `init-common --level domain`（+ 修正 global 三级）

**Files:**
- Modify: `scripts/wiki_engine/cli.py`
- Test: `scripts/wiki_engine/tests/test_cli.py`

**Interfaces:**
- Consumes: Task 2 的三级 `_common_target_path`。
- Produces: `init-common --level domain --type <t> --name <n> --wiki-base <base> --domain <d>` → 在 `<base>/<d>/_common/<n>.md` 生成；`init-common --level global --wiki-base <base>` → 在 `<base>/_common/<n>.md` 生成（修正后）。

> 为什么改 global：`cmd_init_common` 旧代码用 `doc_root=join(wiki_base,"_placeholder")`，依赖 `_common_target_path` 旧 global＝`dirname(doc_root)`。Task 2 把 global 改成 `dirname(dirname(doc_root))` 后，旧 placeholder 会把 global `_common` 落到 `dirname(wiki_base)`（错位）。故须把 placeholder 垫深一级。`_placeholder`/`_d` 仅用于路径数学，不落盘。

- [ ] **Step 1: 写失败测试**

在 `scripts/wiki_engine/tests/test_cli.py` 的 `CliTest` 类内追加两个方法：

```python
    def test_init_common_domain(self):
        wiki = os.path.join(self.tmp, "wiki")
        os.makedirs(os.path.join(wiki, "old_project", "fabusurfer"))
        code, out = _run("init-common", "--level", "domain", "--type", "glossary",
                         "--name", "shared-terms", "--wiki-base", wiki, "--domain", "old_project")
        self.assertEqual(code, 0)
        data = json.loads(out)
        created = data["created"].replace("\\", "/")
        self.assertTrue(created.endswith("old_project/_common/shared-terms.md"), created)
        with open(data["created"], encoding="utf-8") as fh:
            self.assertIn("level: domain", fh.read())

    def test_init_common_global_under_wiki_base(self):
        wiki = os.path.join(self.tmp, "wiki")
        os.makedirs(wiki)
        code, out = _run("init-common", "--level", "global", "--type", "glossary",
                         "--name", "company-terms", "--wiki-base", wiki)
        self.assertEqual(code, 0)
        data = json.loads(out)
        created = os.path.normpath(data["created"])
        self.assertEqual(created, os.path.normpath(os.path.join(wiki, "_common", "company-terms.md")))
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -X utf8 scripts/wiki_engine/tests/test_cli.py -v`
Expected: FAIL — `test_init_common_domain`：`--level domain` 不在 argparse choices → exit 2（`code==0` 断言失败）。`test_init_common_global_under_wiki_base`：global 旧 placeholder 在 Task 2 新路径数学下落到 `dirname(wiki)/_common`，`created` 不等于 `<wiki>/_common/...`。

- [ ] **Step 3: 实现**

在 `scripts/wiki_engine/cli.py` 的 `cmd_init_common`，把（约 line 147-153）
```python
    doc_root = args.doc_root
    if args.level == "global":
        if not args.wiki_base:
            raise UsageError("global 级别需 --wiki-base", code="E_USAGE")
        doc_root = os.path.join(args.wiki_base, "_placeholder")  # dirname(doc_root)==wiki_base
    elif not doc_root:
        raise UsageError("repo 级别需 --doc-root", code="E_USAGE")
```
改为
```python
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
```

把（约 line 162）
```python
    level_zh = "仓库级" if args.level == "repo" else "全局"
```
改为
```python
    level_zh = {"repo": "仓库级", "domain": "域级", "global": "全局"}.get(args.level, args.level)
```

在 `build_parser()` 的 init-common 子解析器处，把（约 line 238）
```python
    ic.add_argument("--level", required=True, choices=["repo", "global"])
```
改为
```python
    ic.add_argument("--level", required=True, choices=["repo", "domain", "global"])
```
并在该子解析器的 `--wiki-base` 行（约 line 242）之后加一行：
```python
    ic.add_argument("--domain", dest="domain", default=None)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -X utf8 scripts/wiki_engine/tests/test_cli.py -v`
Expected: PASS（新 2 个 init-common 测试 + 既有 CLI 测试）。

- [ ] **Step 5: 跑全套回归**

Run: `python -X utf8 -m unittest discover scripts/wiki_engine/tests`
Expected: OK（全绿）。

- [ ] **Step 6: 提交**

```bash
git -C D:/jk_file/skills add document-systems/scripts/wiki_engine/cli.py document-systems/scripts/wiki_engine/tests/test_cli.py
git -C D:/jk_file/skills commit -m "feat(engine): init-common --level domain; fix global path to three-level"
```

---

## Self-Review

**Spec coverage（设计 §5.3 / §4.3）：** `level` 枚举加 domain = Task 1；`_common_target_path` 三级 + promote domain 文案 = Task 2；`init-common` domain + global 修正 = Task 3。链接深度（§4.3）由 `_common_target_path.rel_display` 三行体现并被 promote 用；引用方深度错误由现有 `LINK_TARGET_EXISTS` 兜（设计 §5.3 已述，无需新 lint）。**不在本计划**：根文档 `仓内公共文档` 索引对 domain/global 的链接（`_root_common_index_entry` 硬编码 `./_common/`）属 Plan 4 的根文档/skill 范畴；域 `index.md`=Plan 3；skill 调用=Plan 4。

**Placeholder scan：** 无 TBD / 省略；每个代码步给完整 before→after。

**Type consistency：** `_common_target_path` 返回 `(abspath, rel_display)` 三分支键一致；`level_zh` 字典在 ops 与 cli 两处同形（`repo/domain/global → 仓库级/域级/全局`）；测试断言的 rel（`../_common/` domain、`../../_common/` global）与实现一致。

**回归自查：** Task 2 改 global 语义会动既有 `test_promote_to_common_global_path` → 已在 Task 2 Step 1 整体替换（旧→domain，新增 global），不会留下断言旧二级语义的测试。Task 3 的 global placeholder 垫深与 Task 2 的 `dirname(dirname)` 对齐。

---

## 后续计划

- **计划 3**：`update_domain_index`（薄域 `index.md` 生成）。
- **计划 4**：两个 SKILL.md Phase 1.0 接 `resolve-domain` + 询问编排 + `--init-domains`/`--domain-index`；根文档 `仓内公共文档` 对 domain/global 链接；契约/模板/MAINTAINER。
- **计划 5**：用改造后的 skill 跑 `D:\wiki` 存量迁移（即验证）。
- **承接 Plan 1 的遗留**：`load_registry` 对损坏 `.wiki.json` 抛 `ParseError`（exit 7）——可并入计划 3 或 4。
