# 域分层实现计划 5 / 6 — agent-prose 层（两 SKILL.md + 契约 + MAINTAINER/MIGRATION）

> **状态**：spec（prose 层，非纯 TDD）。执行方式见下「执行与验证」。

**Goal:** 把 Plan 1-4 已完成的引擎能力接进 skill 编排与契约文档：两个 `SKILL.md` 的 Phase 1.0 调 `resolve-domain` 并插入域、加 `--init-domains`/`--domain-index` flag 与自动刷新、wiki-refine 促成 domain；`common-conventions`/`root-architecture` 模板/`refine-subagent-prompt`/`MAINTAINER`/`MIGRATION` 同步到三级 common + 域层。

**为什么非 TDD：** 这些是 skill agent 运行时**读的 prose**（markdown），不是 Python。引擎行为已由 Plan 1-4 的代码 + 单测锁定；本层只改"指导 agent 的话"。验证＝① 引擎全套测试仍绿（确认没误伤代码）；② 逐条对 `MAINTAINER.md` 静态检查；③ 一次性 prose 评审（对设计 §4.3/§5.x + MAINTAINER）；④ **真正的证明是 Plan 6**：用改造后的 skill 跑 `D:\wiki` 存量迁移。

## 执行与验证（适配 prose 的 SDD）

按文件分 4 个编辑任务，主 agent 直接编辑（作者即主 agent，最有上下文），每任务后：`python -X utf8 -m unittest discover scripts/wiki_engine/tests` 仍绿 + 自查 MAINTAINER 相关条目。全部完成后派一个评审子代理通览全部 prose 改动（对 MAINTAINER + 设计）。提交按任务粒度。

---

## Task 1 — `document-systems/SKILL.md`（迁移关键）

**1a. Phase 1.0 路径派生加域。** §1.0 步骤 3「Derive the path set」改为：
- `DOMAIN` = 见新步骤 3b 解析；
- `DOC_ROOT = <WIKI_BASE>/<DOMAIN>/<REPO_NAME>`；`DOC_REL = <DOMAIN>/<REPO_NAME>`；`DOC_GIT_ROOT = <WIKI_BASE>`（不变）。

**1b. 新增 §1.0 步骤 3b「Resolve DOMAIN」**（引擎确定性子命令 + skill 询问编排，对应设计 §5.2）：
- `<ENGINE_CLI>` = 本 skill 安装根下 `scripts/wiki_engine/cli.py`（document-systems 即安装根；用本 SKILL 所在目录）。
- 跑 `python -X utf8 <ENGINE_CLI> resolve-domain --repo <REPO_ROOT> --wiki <WIKI_BASE>`，解析 JSON：
  - `{"status":"resolved","domain":D}` → `DOMAIN=D`。
  - `{"status":"no_registry","candidate":C}` → 首次：`AskUserQuestion`「未发现域配置。以父目录名 `C` 建首个域并归入本仓？」选项「是，建域 C（推荐）」/「自定义域名」；得 `<d>` 后 `resolve-domain … --set <d>`，`DOMAIN=<d>`。
  - 非零退出 `{"code":"E_UNKNOWN_DOMAIN","detail":{"candidate":C,"domains":[…]}}`（exit 10）→ `AskUserQuestion`：选某个已有域 / 把 `C` 注册为**新域**；选"新域"再弹一次确认「确认把 `C` 加入 domains 白名单？」，确认才 `--set C`。**无"本仓 flat"选项**（域强制）。
- 用户取消/拒绝建域 → 中止本次运行并提示（不静默扁平）。

**1c. Arguments 加 flag：**
- `--init-domains`：仅跑/建 `.wiki.json`（交互建域名单），不生成文档。
- `--domain-index[=<domain>]`：仅重建域 `index.md`（`update-domain-index`）；省略值＝当前仓所属域。

**1d. Phase 6 收尾自动刷域 index：** 任一 multi/single 仓生成完成后，跑 `python -X utf8 <ENGINE_CLI> update-domain-index --wiki <WIKI_BASE> --domain <DOMAIN>`，并在 wrap-up 列出 `<DOC_ROOT>/../index.md`（域索引）。

**1e. Hard Constraints 写边界放宽：** "只写 `<DOC_ROOT>` 与 wiki `.gitignore`" → 增加"引擎维护的 `<WIKI_BASE>/<DOMAIN>/index.md` 与 `<WIKI_BASE>/.wiki.json`"（设计 §5.4 写边界）。

**1f. `## Single mode overrides` 同步**（MAINTAINER §9）：single 也走 3b 域解析 + Phase 6 域 index。

**验证：** 引擎测试仍绿；MAINTAINER §7（DOC_ROOT/REL 含域、写边界）、§8（两 skill 解析一致）相关条目自查。

---

## Task 2 — `wiki-refine/SKILL.md`

**2a. Phase 1.0 镜像域解析。** §1.0 步骤 2 的 `DOC_ROOT/DOC_REL` 改为含 `<DOMAIN>`；§1.0.b 已解析 `<ENGINE_CLI>`，复用它跑 `resolve-domain`（与 document-systems 同逻辑 + 同 `AskUserQuestion` 编排）。两 skill 调**同一** `resolve-domain`，天然不漂移（MAINTAINER §8）。
**2b. Phase 1.3 common 上下文加域级。** `<COMMON_CONTEXT>` 除仓级 `<DOC_ROOT>/_common` + 全局 `<WIKI_BASE>/_common`，再列**域级** `<WIKI_BASE>/<DOMAIN>/_common`。
**2c. Phase 2.5.b 促成门禁支持 `level=domain`。** 公共化级别从 repo/global 扩到 repo/domain/global；`global`/`domain` 均须在门禁显式声明并经用户确认（common-conventions §3 默认 repo）。
**2d. `--lint` / Single overrides** 随 `DOC_ROOT` 含域自动正确（无额外改）。

**验证：** 引擎测试绿；MAINTAINER §8/§9 自查。

---

## Task 3 — 契约 / 模板 / refine 子代理 prompt

**3a. `references/common-conventions.md`：**
- §1 目录命名空间表：加一类"**域目录**"——顶层非 `_`/`.` 且在 `.wiki.json domains` 中＝domain（其下才是业务仓）；业务仓判别相应改为"domain 目录下、非 `_`/`.`"。
- §2 两级 common → **三级**：引用路径表换成设计 §4.3 三行版（子系统/仓根 各 → 仓 `./_common/` 或 `../_common/`、域 `../_common/` 或 `../../_common/`、全局再深一级）。
- §3 放置阶梯 3 档 → **4 档**（加"③本域 ≥2 仓共享 → 域级"）。
- §7 frontmatter `level: repo | global` → `repo | domain | global`（与引擎 `COMMON_LEVELS` 一致，Plan 2 已落）。
- §6 派生索引 carve-out：注明域级 `index.md` 也是引擎维护的薄索引（Plan 3）。
**3b. `references/templates/root-architecture.md`：**
- 占位符定义 `<DOC_ROOT>`=`<WIKI_BASE>/<DOMAIN>/<REPO_NAME>`、`<DOC_REL>`=`<DOMAIN>/<REPO_NAME>`（line 16/18）。
- `## 仓内公共文档` 引言（line 134）改三级措辞：仓 `./_common/`、域 `../_common/`、全局 `../../_common/`。
- `<REPO_COMMON_INDEX_ROWS>` 生成说明（line 70-75）：init 扫 `<DOC_ROOT>/_common/` 仅列仓级；域/全局行由引擎 `update_root common_index_entry`（按 level 出 `../_common/`/`../../_common/`，Plan 4 已落）后续维护。
**3c. `wiki-refine/references/refine-subagent-prompt.md`：**
- line 13「two-level `_common`」→ three-level；line 69「repo vs global」→「repo vs domain vs global，默认 repo」；line 28 `<COMMON_CONTEXT>` 含域级；line 37 single-mode 促成「level=global」→「domain 或 global」（单系统仓仍在某域内）；line 85 `promote_to_common {level}` 注明 level ∈ repo|domain|global。

**验证：** 引擎测试绿（契约是 .md，不动代码）；MAINTAINER §11（章节名常量 ↔ 模板/契约，含 level 名）自查；§10 双向（契约加 domain 档，引擎 lint 已有，Plan 2）。

---

## Task 4 — `MAINTAINER.md` / `MIGRATION.md`

**4a. `MAINTAINER.md`：**
- §7：DOC_ROOT/REL 含 `<DOMAIN>`；`.wiki.json`（域注册表，committed）；写边界放宽到域 `index.md` + `.wiki.json`。
- §8：两 skill 经**同一** `resolve-domain` 解析域（去重保证）。
- §11：章节名/常量集加 `level` 三值（repo/domain/global）、域 `index.md`、`_root_common_index_entry` 的 level→prefix 映射。
- 新增检查：`.wiki.json` 注册表存在性 + 域强制（无 flat 分支）；越界 `level` 引擎应报 `UsageError`（Plan 4 final review 建议——若实现则同步此检查；本计划记为待办）。
**4b. `MIGRATION.md`：** 加 **M0 — 域化迁移**：建 `.wiki.json`（`--init-domains`）→ `git mv <repo> <domain>/<repo>`（仓内相对链接不破，实测 0 个 `](../../)`）→ 对受影响仓 `--step=root` 重生成（根样板刷三级）→ `resolve-domain --set` 固化 repos 映射 → `--domain-index` 生成域索引。M1-M5 原样保留，纳入同一治理窗口。

**验证：** prose；MAINTAINER 自身一致性（§15 算子名含 `update_domain_index`）。

---

## 后续

- **计划 6**：用改造后的 skill 真跑 `D:\wiki` 存量迁移（M0），即对全链路的端到端验证；产出两域 wiki + 域 index + `.wiki.json`。
- **Plan 4 carry-forward（可在本计划或 6 处理）**：引擎对越界 `level` 报错；合并 repo/domain/global↔中文 三处映射消重。
