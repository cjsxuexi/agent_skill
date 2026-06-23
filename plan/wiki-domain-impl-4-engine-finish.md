# 域分层实现计划 4 / 6 — 引擎收尾（根文档 common 索引分级 + init-common 入参校验）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 收尾引擎侧最后两处与 domain 相关的代码：① 根文档 `## 仓内公共文档` 索引条目按 common 级别给出正确链接深度（repo `./_common/`、domain `../_common/`、global `../../_common/`）；② `init-common` 对所有级别统一校验目标父目录存在（关闭 Plan 2/3 遗留：避免 typo 静默造幽灵目录）。

**Architecture:** 纯引擎、纯 TDD。两处独立小改：`ops/__init__.py` 的 `_root_common_index_entry`（加 `level` → 链接前缀 + 级别中文），`cli.py` 的 `cmd_init_common`（写盘前 `isdir(base)` 校验，`base = dirname(dirname(abspath))` 对三级一致）。

**Tech Stack:** Python 3.8+ 标准库；`unittest`；引擎现有 `ops`、`cli`。

## Global Constraints

- **根文档视角的链接深度（§4.3 仓根行）**：repo `./_common/`、domain `../_common/`、global `../../_common/`。`_root_common_index_entry` 的行链接必须按 common 级别取这三者之一。
- **向后兼容**：不传 `level` 时默认 `repo`（行为同现状，链接 `./_common/`，级别"仓库级"）；既有 `test_update_root_common_index_creates_section` 须仍绿。
- **init-common 统一校验**：repo/domain/global 三级都要求"目标 `_common` 的父目录"已存在（repo→`<doc_root>`、domain→`<wiki_base>/<domain>`、global→`<wiki_base>`），缺失则 `UsageError`(exit 2)。统一用 `base = os.path.dirname(os.path.dirname(abspath))`。
- **仅标准库；UTF-8/原子写**；引擎错误带 `code`+`message_zh`；CLI 每次一个 JSON。
- **不破坏既有引擎**：`python -X utf8 -m unittest discover scripts/wiki_engine/tests`（cwd=`D:\jk_file\skills\document-systems`）全绿。**改共享行为的任务收尾跑全套**。
- **命令工作目录** = `D:\jk_file\skills\document-systems`；`python -X utf8`；提交走 `git -C D:/jk_file/skills`。

---

## File Structure

- `scripts/wiki_engine/ops/__init__.py` —（改）`_root_common_index_entry` 分级链接 + 创建段落 intro 中性化。
- `scripts/wiki_engine/tests/test_ops.py` —（改）既有 repo 用例保留；新增 domain/global 用例。
- `scripts/wiki_engine/cli.py` —（改）`cmd_init_common` 加 `isdir(base)` 校验。
- `scripts/wiki_engine/tests/test_cli.py` —（改）新增"域目录不存在→报错"用例。

---

## Task 1: 根文档 common 索引条目分级链接

**Files:**
- Modify: `scripts/wiki_engine/ops/__init__.py`
- Test: `scripts/wiki_engine/tests/test_ops.py`

**Interfaces:**
- Produces: `update_root` 的 `common_index_entry` 接受可选 `level ∈ {repo,domain,global}`（默认 `repo`）：行链接前缀 `./_common/` / `../_common/` / `../../_common/`；`级别` 列＝`op["级别"]`（若给）否则按 level 映射"仓库级/域级/全局"。

- [ ] **Step 1: 写失败测试**

在 `scripts/wiki_engine/tests/test_ops.py` 中，在 `test_update_root_common_index_creates_section` 之后追加两个方法：

```python
    def test_update_root_common_index_domain_link(self):
        txn = self._root_txn()
        op = {"op": "update_root", "target": "architecture.md", "kind": "common_index_entry",
              "action": "add", "name": "coord-terms", "level": "domain",
              "类型": "glossary", "说明": "坐标/航向术语"}
        res = ops.op_update_root(txn, op, 0)
        rel, before, after = _apply(res, txn)
        self.assertIn("[coord-terms](../_common/coord-terms.md)", after)
        self.assertIn("域级", after)

    def test_update_root_common_index_global_link(self):
        txn = self._root_txn()
        op = {"op": "update_root", "target": "architecture.md", "kind": "common_index_entry",
              "action": "add", "name": "company-std", "level": "global",
              "类型": "infra", "说明": "全公司约定"}
        res = ops.op_update_root(txn, op, 0)
        rel, before, after = _apply(res, txn)
        self.assertIn("[company-std](../../_common/company-std.md)", after)
        self.assertIn("全局", after)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -X utf8 scripts/wiki_engine/tests/test_ops.py -v`
Expected: FAIL — 两个新用例失败：当前 `_root_common_index_entry` 硬编码 `./_common/`，断言 `../_common/` / `../../_common/` 落空。

- [ ] **Step 3: 实现**

在 `scripts/wiki_engine/ops/__init__.py` 把 `_root_common_index_entry`（约 line 373-393）整体替换为：

```python
_COMMON_LINK_PREFIX = {"repo": "./_common/", "domain": "../_common/", "global": "../../_common/"}
_COMMON_LEVEL_ZH = {"repo": "仓库级", "domain": "域级", "global": "全局"}


def _root_common_index_entry(txn, doc, op, rel, res):
    name = op["name"]
    level = op.get("level", "repo")
    prefix = _COMMON_LINK_PREFIX.get(level, "./_common/")
    level_zh = op.get("级别") or _COMMON_LEVEL_ZH.get(level, level)
    ctype = op.get("类型", "")
    desc = op.get("说明", "")
    row_cells = ["[{}]({}{}.md)".format(name, prefix, name), level_zh, ctype, desc]
    sec = doc.section_by_title("仓内公共文档")
    if sec is not None:
        _append_table_row(doc, sec, row_cells, rel, res)
        return
    # create the `## 仓内公共文档` section before `## 辅助资源`
    aux = _region_section(doc, "辅助资源")
    block = (
        "## 仓内公共文档\n\n"
        "跨层级共享、无单一属主的事实由相应级别的 `_common/` 持有"
        "（仓内 `./_common/`、域内 `../_common/`、全局 `../../_common/`）；"
        "子系统文档以锚点引用、不复制其内部细节。\n\n"
        "| 公共文档 | 级别 | 类型 | 说明 |\n"
        "|---|---|---|---|\n"
        "| " + " | ".join(row_cells) + " |\n\n"
    )
    res.add_edit(rel, Edit(aux.start, aux.start, block))
```

（注：把两个映射常量 `_COMMON_LINK_PREFIX` / `_COMMON_LEVEL_ZH` 放在函数前。其余 `_ROOT_KINDS` 注册不变。）

- [ ] **Step 4: 跑测试确认通过**

Run: `python -X utf8 scripts/wiki_engine/tests/test_ops.py -v`
Expected: PASS（新 domain/global 用例 + 既有 `test_update_root_common_index_creates_section`（repo，`./_common/`）仍绿）。

- [ ] **Step 5: 提交**

```bash
git -C D:/jk_file/skills add document-systems/scripts/wiki_engine/ops/__init__.py document-systems/scripts/wiki_engine/tests/test_ops.py
git -C D:/jk_file/skills commit -m "feat(engine): root common-index entry links by level (repo/domain/global)"
```

---

## Task 2: `init-common` 统一入参校验

**Files:**
- Modify: `scripts/wiki_engine/cli.py`
- Test: `scripts/wiki_engine/tests/test_cli.py`

**Interfaces:**
- Produces: `cmd_init_common` 写盘前校验目标 `_common` 的父目录存在（repo→`<doc_root>`、domain→`<wiki_base>/<domain>`、global→`<wiki_base>`），缺失抛 `UsageError`(exit 2)；存在则照常生成。

> 关闭 Plan 2/3 遗留（final review 建议"统一入参校验"）。`base = os.path.dirname(os.path.dirname(abspath))` 对三级都等于"应包含 `_common` 的目录"，故一处校验覆盖全部。

- [ ] **Step 1: 写失败测试**

在 `scripts/wiki_engine/tests/test_cli.py` 的 `CliTest` 类内追加：

```python
    def test_init_common_domain_missing_domain_dir_errors(self):
        wiki = os.path.join(self.tmp, "wiki")
        os.makedirs(wiki)  # wiki 存在，但 wiki/ghost 域目录不存在
        code, out = _run("init-common", "--level", "domain", "--type", "glossary",
                         "--name", "x", "--wiki-base", wiki, "--domain", "ghost")
        self.assertEqual(code, 2)
        data = json.loads(out)
        self.assertEqual(data["code"], "E_USAGE")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -X utf8 scripts/wiki_engine/tests/test_cli.py -v`
Expected: FAIL — 当前 `cmd_init_common` 不校验父目录，会直接写出 `wiki/ghost/_common/x.md` 并 exit 0；断言 `code==2` 失败。

- [ ] **Step 3: 实现**

在 `scripts/wiki_engine/cli.py` 的 `cmd_init_common` 中，找到取得 `abspath` 的那行（约 line 170）：
```python
    abspath, rel_display = ops_mod._common_target_path(mt, args.level, args.name)
```
在其**之后、`if os.path.exists(abspath):` 之前**插入：
```python
    base = os.path.dirname(os.path.dirname(abspath))
    if not os.path.isdir(base):
        raise UsageError("目标目录不存在：{}（请先建立该仓/域/wiki 目录）".format(base),
                         code="E_USAGE")
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -X utf8 scripts/wiki_engine/tests/test_cli.py -v`
Expected: PASS（新用例 + 既有 `test_init_common_domain`/`test_init_common_global_under_wiki_base`——它们已建好对应目录，校验通过）。

- [ ] **Step 5: 跑全套回归**

Run: `python -X utf8 -m unittest discover scripts/wiki_engine/tests`
Expected: OK（全绿）。

- [ ] **Step 6: 提交**

```bash
git -C D:/jk_file/skills add document-systems/scripts/wiki_engine/cli.py document-systems/scripts/wiki_engine/tests/test_cli.py
git -C D:/jk_file/skills commit -m "fix(engine): init-common validates target parent dir exists (all levels)"
```

---

## Self-Review

**Spec coverage：** 根文档 common 索引分级链接（§4.3 仓根行）= Task 1；init-common 统一入参校验（Plan 2/3 遗留）= Task 2。**不在本计划**：wiki-refine 2.5.b 促成 domain `level` 时把 `level` 传进 `common_index_entry`（skill prose，Plan 5）——本计划只让引擎"能"按 level 出正确链接。

**Placeholder scan：** 无 TBD / 省略；每步完整代码。

**Type consistency：** `level ∈ {repo,domain,global}`；`_COMMON_LINK_PREFIX`/`_COMMON_LEVEL_ZH` 键一致；`base = dirname(dirname(abspath))` 对三级语义一致（=应含 `_common` 的目录）；既有 repo 用例不传 `level` 默认 repo、链接 `./_common/` 不变。

**回归自查：** Task 1 默认 repo 路径＝原行为，既有 common-index 用例不动；Task 2 仅在"父目录不存在"时新增报错，既有 domain/global 用例已建目录、不受影响；Task 2 收尾跑全套。

---

## 后续计划

- **计划 5**：agent-prose 层——`document-systems/SKILL.md` + `wiki-refine/SKILL.md` 的 Phase 1.0 接 `resolve-domain` + 询问编排 + `--init-domains`/`--domain-index`（Phase 6 自动刷域 index）+ wiki-refine 2.5.b 促成 domain（传 `level`）；`common-conventions.md` §1/§2/§3/§7；`templates/root-architecture.md`；`MAINTAINER.md`/`MIGRATION.md` 同步。验证：MAINTAINER 静态检查 + 引擎测试 + 评审（非单测 TDD）。
- **计划 6**：用改造后的 skill 跑 `D:\wiki` 存量迁移（git mv 各仓入域 + `--step=root` 重生成 + `--domain-index`），即验证。
