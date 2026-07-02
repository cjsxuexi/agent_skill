# 生产问题速查 专用 Skill 实施计划（prod-issue-quickref）· rev.2（+ 自启动记录）

> **给评估者（本文件用途）**：待评估计划，非直接执行清单。第 3 节「设计决策」是需你拍板处；重点看新增的 **DA（自启动触发机制）/ DB（记 vs 问 vs 跳过门禁）**。确认/改动后再进入执行。
> **给执行者（评估通过后）**：按任务逐条实现；推荐 superpowers:subagent-driven-development 或 executing-plans。步骤用 `- [ ]` 勾选。
> **rev.2 变更**：① 文档形态由「表格」改为**已定稿的诊断树**（第 2 节全改）；② 新增头号需求 **自启动记录**（定位类 session 结束时自动更新速查，不确定就先问用户）——见 DA/DB 与 Task 6。架构随之从「纯 prose」变为「prose + 少量脚本（hook + 校验器）」。

**Goal（一句话）**：做一个 skill，(a) 在 D:\wiki 体系里为任意仓**维护**「生产问题速查.md」诊断树（现象→根因，薄、链出）；(b) **在"分析定位问题"类 session 结束时自启动**——自动把本次定位到的问题记入对应速查；**不确定是否该记就先问用户**。

**Architecture（3 句）**：`SKILL.md`（prose）承载记录/询问/消费逻辑；**定位/域解析复用现成 `wiki_engine resolve-domain` 与 `.document-systems.json`**，不新建引擎。**自启动靠 Claude Code 的 `Stop` hook**（settings.json）实现——一个 prose skill 无法在 session 结束时自己触发，必须由 hook 驱动。文档写入是对**诊断树嵌套 bullet 的受约束追加**，配一个**必跑的只读校验器**（自动写入无人复核，安全性靠校验兜底）。

**Tech Stack**：Markdown（SKILL.md/references）；Python 3（`resolve-domain` 调用 + hook 脚本 + 校验器，全部 `-X utf8`）；Claude Code hooks（`Stop` 触发 + `PostToolUse` 布防，配在 settings.json）；Windows PowerShell 5.1 / Git Bash；无新增三方依赖。

## Global Constraints（每个任务隐含遵守）

- **薄**：速查只有「用法说明 + `##` 现象根 + 判别分支 → 根因叶子（一句话+wiki链接）」。**禁止**在树里写完整分析/恢复缓解/待确认/证据/时间线——进被链接的 wiki 文档（SUP-23 用户定义）。
- **诊断树三档标识符规则**：现象节点自然语言、可整合多情况、不必逐字；**根因叶子 + 判别信号里的代码/日志标识（接口/类/Mapper/表/错误类/日志关键字）一律原样**。
- **复用不重造**：定位/域解析走 `wiki_engine resolve-domain`；不复制 WIKI_BASE/域逻辑。
- **不碰源码仓**：只写 `<WIKI_BASE>` 下文件；不改被文档化的源码仓。
- **自启动是"记录/询问"，不是"分析"**：hook 只负责在 session 尾把「是否记录」这件事推到台前；真正判断与写入由模型按 SKILL.md 做。**不确定就问用户，绝不静默瞎记，也不静默漏记明确定位到的问题**。
- **编码安全（Windows）**：中文正文走文件（file-write / `--content-file`），不经 PowerShell stdin 管道传原生程序；Python 一律 `python -X utf8`。
- **落地目录**：skill 源码在 `D:\jk_file\skills\prod-issue-quickref\`（本 git 仓），装到 `C:\Users\admin\.claude\skills\prod-issue-quickref\`；hook 配置进 `C:\Users\admin\.claude\settings.json`。本计划在 `D:\jk_file\skills\plan\`。

---

## 1. 背景与既有事实（自足）

- **文档形态已定稿 = 诊断决策树**（差异诊断风格，非故障树 FTA；随事故增量生长）。样板：`D:\wiki\old_project\fabusurfer\生产问题速查.md`（当前唯一实例，已含 2 条根因挂在「云控卡顿」一棵下）。
- 用户对这类文档的定义（累计）：**agent 按现象快速圈定几个候选根因、指导程序员确认**；只做定位不做分析；**用链接关联其他 wiki**；薄；现象自然语言、根因标识原样。
- **新需求（本轮）**：**自启动记录**——定位类 session 结束时自动更新对应速查；**不确定是否要记，先主动问用户**。
- 定级：仓库级，落 `<WIKI_BASE>/<DOMAIN>/<REPO>/生产问题速查.md`（仓根）；不进 `_common/`（非其四类）。
- 既有引擎事实（已核实）：`WIKI_BASE` 配置 `C:\Users\admin\.document-systems.json` → `D:\wiki`；引擎 CLI `…\document-systems\scripts\wiki_engine\cli.py`（有 `resolve-domain`/`outline`/`refs`/`lint` 等）；`resolve-domain --repo <R> --wiki <W>` 打印 `{"…","domain":<父目录名>}`；引擎 `ignore-globs`（`common-conventions.md` §10）：`issue/**`、`whole_architecture.md`、`spec/**`、`**/.review.md`——**速查文档不在内**（见 D6）。
- **Claude Code hooks 事实（已核实，[Hooks reference](https://code.claude.com/docs/en/hooks)）**：
  - `Stop` hook 每轮结束（模型停下）触发；返回 `{"decision":"block","reason":"<文本>"}`（或 exit 2）会**阻止停止**、把 `reason` 注入、让模型**多跑一轮**去做被要求的事。这是"session 尾自启动记录/询问"的落点。
  - hook 输入（stdin JSON）含 `session_id`、`transcript_path`、`stop_hook_active`（上一次 stop 是否已被 hook 续过——用它防死循环）。
  - `SessionEnd` hook 仅用于清理/日志，**不能与模型交互**，无法驱动"记录或询问"，故不用它。
  - 配置在 settings.json：`hooks.<Event>[].matcher` + `hooks[].command`。

---

## 2. 文档 Schema（诊断树，已锁定，执行者照抄）

以 fabusurfer 实例为准：

```markdown
---
title: <仓中文名> 生产问题速查（现象 → 根因诊断树）
scope: 仓库级 / <REPO>（<系统别名>）
created: <YYYY-MM-DD>
updated: <YYYY-MM-DD>
tags: [<repo>, 生产问题, 速查, 诊断树]
status: active
---

# <仓中文名> 生产问题速查（现象 → 根因诊断树）

> **用法**：从匹配的「共有现象」（`##` 根）进入，用「细分现象 / 判别信号」逐层收窄，到叶子拿到候选根因 + 去哪确认。
> **同一现象通常对应多个根因，务必沿判别信号走到叶子，别在根节点就下结论。**
> **只定位、不分析**：叶子只给一句话根因 + wiki 链接；完整链路 / 证据 / 修复在被链接的 wiki 文档里。
> **记录约定**：现象节点用可归纳的自然语言（可整合多种情况，不必逐字）；根因与判别信号里的代码标识（接口 / 类 / Mapper / 表 / 错误类 / 日志关键字）一律原样保留。
> **新增**：找到对应「共有现象」根，在其下加「判别分支 → 根因叶子」；无匹配根则新起一个 `##` 现象。

## <共有现象>（自然语言，可归纳多种表现）

- **判别**：<把候选根因区分开的观测/信号，含代码/日志标识、原样>
  - **根因**：<一句话根因链，标识原样>。**确认** → [<wiki 文档 / 章节>](<相对链接#锚点>)
- **判别**：<另一条分支>
  - **根因**：<...>。**确认** → [<...>](<...>)
```

**节点规则：**
- `## <共有现象>`：主诉现象（根）。自然语言、可归纳。**仅当没有已存在的现象根能匹配时才新建**。
- `- **判别**：<信号>`：把候选根因区分开的观测（这是"指导程序员确认"的抓手）；含标识符原样。
- `  - **根因**：<一句话> **确认** → [链接]`：叶子。标识原样；**必须**链到一篇**已存在**的 wiki 文档（架构 §/ troubleshooting / `_common`）。
- **可加深**：现象根 → 细分现象 → 判别 → 根因，按需再缩进一层 bullet。
- **禁止**：叶子里堆时间线/证据/恢复步骤/待确认。

---

## 3. 设计决策（★ 需你评估）

### DA — 自启动触发机制（★ 本轮头号）

一个 prose skill 无法在 session 结束时自触发 → **必须用 hook**。方案：

- **推荐：`Stop` hook（布防式）**。逻辑：session 里发生"定位类"活动时**布防**一个 per-session marker；`Stop` hook 每轮尾读该 marker，**仅当已布防且本 session 尚未处理过**时，返回 `{"decision":"block","reason":<让模型跑记录/询问流程>}` 让模型多跑一轮去记录或询问，随即置"已处理"marker 防重复/死循环（配合 `stop_hook_active`）。
  - **布防怎么来（可靠、少依赖模型记性）**：用 `PostToolUse` hook——当模型 `Read` 的目标是某仓 `生产问题速查.md`，或运行了诊断类 skill（如 `fms-diagnose`）时，自动 `touch` 布防 marker。即"**消费即布防**"：一旦本 session 查过速查/做过诊断，session 尾就会被推着问"要不要记"。
  - **诚实的边界**：只覆盖"读过速查 / 用过诊断 skill"的 session；对"全新现象、既没查速查也没用诊断 skill"的定位，hook 不布防 → 由 SKILL.md 让模型在自然收尾时兜底自查（best-effort），或用户手动 `/prod-issue-quickref add`。
- 备选 1：`Stop` hook **每 session 无条件问一次**（per-session "已问"guard）。可靠但会给**所有** Claude Code session 尾加一轮"要不要记"判断（非定位 session 模型秒答"否"）——偏吵。
- 备选 2：`Stop` hook 每轮扫 `transcript_path` 找"根因/定位/排查"关键字判断是否定位 session。无 marker 耦合，但模糊、偏重。
- 不用 `SessionEnd`（不能交互）。
- **推荐布防式**（精准、不打扰非定位 session）。你可选"无条件问一次"若更看重"绝不漏"。

### DB — 记 / 问 / 跳过 门禁（自启动的判断闸）

被 hook 推起后，模型按此判：
- **有把握记**：本 session 明确定位到一个"值得记"的生产问题根因（有现象 + 定位到根因 + 有可链接的 wiki 文档）→ 直接记（按 Task 5 追加树节点），并告诉用户"已记入：<现象→根因>"。
- **不确定 → 先问**（用户明确要求的行为）：定位不完整 / 不确定是否算生产问题 / 不确定是否该沉淀 → `AskUserQuestion`：「这次定位到的『<现象>→<根因>』要不要记进 生产问题速查.md？」→ 是则记、否则跳过。
- **明确跳过**：本 session 非定位类、或没定位到根因 → 静默结束，不记不问。
- **去重**：记前先在树里查同现象根/同根因；已存在则**加判别分支或合并**，不新起重复节点；完全重复则跳过并告知。
- **推荐**：默认"能确信才自动记，其余一律先问"，把"漏问"看得比"多问一次"更糟。

### D1 — 工具化深度：prose + **必跑校验器**（本轮微调）

- 因为**自启动写入通常无人当场复核**，把上一版"可选的校验器"**升为核心且必跑**：每次追加后（含自启动）必须跑 `validate_quickref.py`，不过则不落盘/回滚并提示。
- 仍**不新建引擎**、不套 architecture 的六通道 lint。
- 升级位（若你要更强确定性）：把追加也做成确定性脚本（解析树 → 定位 `##` 根 → 插入 bullet → 重写），见第 6 节。默认仍由模型按模板追加 + 校验器兜底。

### D4 — 一仓一档（维持）；D5 — 命名；D6 — ignore-globs；D7 — 无 wiki 文档可链（均沿用上一版）

- **D4**：一仓一档，对齐仓库级定级；域级/全局汇总先不做。
- **D5**：暂名 `prod-issue-quickref`。注意：因加了自启动，**写侧不再是纯 manual**——`add`/`init` 仍可手动 `/prod-issue-quickref`，但"自启动记录"由 hook 驱动。名字你定。
- **D6**：把 `生产问题速查.md` 加进引擎 `ignore-globs`（改 `common-conventions.md` §10，一行、可逆）——**需你同意改契约**；否则 `/wiki-refine --lint` 会误报。
- **D7**：找不到深度 wiki 文档时，叶子仍只写一句话根因 + 链最接近的架构章节，并提示"该根因暂无深度文档，建议后续补"（不自动写深度文）。

---

## 4. File Structure（推荐路线下）

- Create `…\prod-issue-quickref\SKILL.md` — 记录/询问/消费主逻辑（prose）。
- Create `…\references\tree-template.md` — 第 2 节树 schema 模板（占位 + 顶部注释）。
- Create `…\references\node-format.md` — 节点三规则 + 从 fabusurfer 抄的真实节点范例 + 校验清单（禁词、必有 `./…md` 链接、标识反引号）。
- Create `…\scripts\validate_quickref.py` — **只读校验器（核心）**：frontmatter + 树结构 + 每叶必含 `./…md` 链接 + 禁词零命中 + 无 `???`。
- Create `…\scripts\quickref_hook.py` — 一个脚本两模式：`--arm`（PostToolUse：命中"读速查/诊断 skill"则布防 marker）、`--stop`（Stop：已布防且未处理则 `block`+reason，并置"已处理"）。marker 放 `<state_dir>/quickref-<session_id>.{armed,done}`。
- Create `…\hooks.settings.snippet.json` — 待并入 `~/.claude/settings.json` 的 `Stop`/`PostToolUse` 片段（安装时合并，见 Task 8）。
- Modify（D6 通过）`…\document-systems\references\common-conventions.md` — ignore-globs 加 `生产问题速查.md`。
- Install：拷贝 skill → `~/.claude/skills\`；合并 hook 片段 → `~/.claude/settings.json`（建议用 `update-config` skill 做，属配置变更，需你同意）。

---

## 5. Tasks

> prose skill 的"测试"= 在真实 wiki 干跑 + 脚本单测。每个任务有可核验交付物。

### Task 1：脚手架 + SKILL.md 骨架
**Files:** Create `SKILL.md`
- [ ] Step 1：建 `prod-issue-quickref\{references,scripts}\`。
- [ ] Step 2：写 frontmatter（name/description）。description 覆盖**三条触发**：报线上现象/问"可能什么原因"（消费）、显式 `/prod-issue-quickref add|init`（手动写）、以及**被 Stop hook 的 reason 唤起时执行"记录/询问"流程**。正文放章节占位：`## 定位文档`、`## 消费（读）`、`## 记录（add/自启动共用）`、`## init`、`## 询问门禁`、`## 校验`。
- [ ] Step 3（核验）：`type SKILL.md` frontmatter 合法。

### Task 2：树模板 + 节点规则（references）
**Files:** Create `references\tree-template.md`、`references\node-format.md`
- [ ] Step 1：`tree-template.md` = 第 2 节树 schema（占位 + 顶部 HTML 注释说明取值，生成时删注释）。
- [ ] Step 2：`node-format.md` = 三节点规则 + 从 `D:\wiki\old_project\fabusurfer\生产问题速查.md` 抄的真实节点（`## 云控卡顿…` 根 + 两条 `- 判别/根因`）+ 校验清单。
- [ ] Step 3（核验）：`grep` 确认范例含 `./port-device/architecture.md#`、`vehicle-status-push-troubleshooting.md`，无 `???`。

### Task 3：定位文档（复用 resolve-domain）
**Files:** Modify `SKILL.md`「定位文档」
- [ ] Step 1：读 `%USERPROFILE%\.document-systems.json` 取 `wiki_base`；`REPO_ROOT=git rev-parse --show-toplevel`（否则 cwd），`REPO_NAME=basename`。
- [ ] Step 2：`python -X utf8 <ENGINE_CLI> resolve-domain --repo <REPO_ROOT> --wiki <WIKI_BASE>` 解析 `domain`；`<ENGINE_CLI>` 按 wiki-refine §1.0.b 探测顺序解析，禁写死用户名。得 `QUICKREF=<WIKI_BASE>/<DOMAIN>/<REPO_NAME>/生产问题速查.md`。
- [ ] Step 3（核验）：给 fabusurfer 期望值（`domain=old_project`，`QUICKREF=D:\wiki\old_project\fabusurfer\生产问题速查.md`）。

### Task 4：校验器（核心，先做，追加要用）
**Files:** Create `scripts\validate_quickref.py`（+ 同文件 `tests`）
- [ ] Step 1：写失败测试：喂"叶子缺 `./…md` 链接""含『恢复方向/待确认』禁词""表头/结构坏"三个坏样例，期望非 0 退出 + 明确原因。
- [ ] Step 2：跑测试确认 FAIL（未实现）。
- [ ] Step 3：实现（只读，`-X utf8`）：解析 frontmatter + `##` 现象根 + `- 判别`/`  - 根因` 缩进树；断言：每 `根因` 叶含 ≥1 个 `./…md` 相对链接、禁词零命中、标识用反引号、无 `???`、缩进合法；打印 JSON 结果。
- [ ] Step 4：跑测试 PASS；对真实 fabusurfer 速查跑一次 PASS。
- [ ] Step 5：commit。

### Task 5：记录流程（add，手动与自启动共用）
**Files:** Modify `SKILL.md`「记录」
- [ ] Step 1：输入（模型从本 session 定位结果收集）：`共有现象`、`判别信号`、`一句话根因`、`根因所在子系统/接口/表标识`。
- [ ] Step 2：**解析链接目标**：在 `<DOC_ROOT>` 内按子系统/接口/类/表匹配已存在文档 + 锚点（优先 `<sub>/architecture.md` 相关 §、其次该子系统 troubleshooting/runbook、再 `_common/`）；锚点用引擎 `outline`/`refs` 或 grep 标题算 GitHub slug。找不到 → D7。
- [ ] Step 3：**find-or-create**：无 `QUICKREF` → 先 init（Task 7）；有 → 读树。
- [ ] Step 4：**定位落点**：树里有匹配 `##` 现象根 → 在其下加 `- 判别 → 根因` 分支（已存在等价分支则合并/跳过，去重）；无匹配根 → 新起 `##` 现象根再加分支。改 frontmatter `updated`。file-write/Edit，UTF-8。
- [ ] Step 5：**必跑校验**：`python -X utf8 scripts\validate_quickref.py <QUICKREF>`；不过 → 回滚该次编辑、报原因（自启动场景下改为"留给用户手动修"）。
- [ ] Step 6（核验，干跑）：往 fabusurfer 速查加一条**合成**分支 → 校验过 → `git -C D:\wiki checkout -- old_project/fabusurfer/生产问题速查.md` 还原。断言：加后校验过、还原无残留。

### Task 6：★ 自启动触发（Stop hook + PostToolUse 布防）
**Files:** Create `scripts\quickref_hook.py`、`hooks.settings.snippet.json`；Modify `SKILL.md`「询问门禁」
- [ ] Step 1：`quickref_hook.py --arm`（PostToolUse）：读 stdin JSON，若 `tool_name==Read` 且 `tool_input.file_path` 以 `生产问题速查.md` 结尾（或命中诊断 skill 标记）→ `touch <state>/quickref-<session_id>.armed`。
- [ ] Step 2：`quickref_hook.py --stop`（Stop）：读 stdin；若 `.armed` 存在、`.done` 不存在、且 `stop_hook_active!=true` → 打印 `{"decision":"block","reason":"<见下>"}` 到 stdout 并 `touch .done`；否则空输出（放行）。reason 文本：「本 session 疑似问题定位。请按 prod-issue-quickref『记录/询问门禁』：若已定位到值得记录的生产问题根因，记入对应仓 生产问题速查.md（现象根→判别→根因叶+wiki链接，跑校验器）；不确定是否该记先问用户；非定位或无根因则直接结束。」
- [ ] Step 3：`hooks.settings.snippet.json` 写 `Stop`（matcher `""` → `quickref_hook.py --stop`）与 `PostToolUse`（matcher `Read` → `quickref_hook.py --arm`）两段。
- [ ] Step 4：`SKILL.md`「询问门禁」写 DB 的记/问/跳过判定 + 去重 + 处理完清 marker 的约定。
- [ ] Step 5（核验，单测）：喂三种 stdin（未布防、已布防未处理、已处理/`stop_hook_active`）给 `--stop`，断言分别输出 空 / block+reason / 空；喂 Read 速查/Read 他文件给 `--arm`，断言分别 布防/不布防。

### Task 7：init（空树脚手架）
**Files:** Modify `SKILL.md`「init」
- [ ] Step 1：以 `tree-template.md` 生成 `<DOC_ROOT>/生产问题速查.md`（填 title/scope/日期/tags/repo），只留用法说明、无 `##` 现象根，删注释。
- [ ] Step 2（核验，干跑）：对无速查的临时 `DOC_ROOT` 跑 init → 断言与第 2 节骨架一致、UTF-8、无 `<...>` 残留；删测试产物。

### Task 8：安装、接线、验收、自查
**Files:** Install skill + 合并 hook 片段（+ D6 通过则 Modify `common-conventions.md`）
- [ ] Step 1：拷贝 skill → `~/.claude/skills\prod-issue-quickref\`。
- [ ] Step 2：把 `hooks.settings.snippet.json` 合并进 `~/.claude/settings.json`（建议 `update-config` skill；**配置变更，需你同意**）。
- [ ] Step 3（自启动端到端验收）：新 Claude Code session → 读一次 fabusurfer `生产问题速查.md`（触发 `--arm` 布防）→ 结束 → 断言 Stop hook `block` 了一轮、模型进入"记录/询问"；喂一个"已定位清楚"的问题应直接记（并跑校验过），喂一个"模糊"的应 `AskUserQuestion` 先问。
- [ ] Step 4（手动写 + 读侧验收）：`/prod-issue-quickref add` 加一条已知云控现象、校验过、`git diff` 仅新增该分支；新会话喂"mysql 1200%+BadSqlGrammar"应据树指向根因①。
- [ ] Step 5（洁净性 / 防扰）：D6 通过则 `/wiki-refine --lint` 不再报速查；确认非定位 session（没读速查）Stop hook **不**打扰。
- [ ] Step 6：过第 9 节自查表。

---

## 6. 升级位：把"追加"也做成确定性脚本（DA/D1 增强时展开）
- `scripts\quickref_apply.py`：解析树 → 定位/新建 `##` 现象根 → 幂等插入 `判别/根因` bullet → 重写 → 内部调校验器。SKILL.md 记录流程改调它，去除"模型手写 bullet"的漂移风险。
- 代价：+~200–300 行 + 树解析/缩进单测；收益：自启动无人复核下写入更稳。若自启动上线后发现漂移，再上此位。

## 7. 验收标准（DoD）
- 定位类 session 结束时能被 hook 推起，按门禁**记 / 问 / 跳过**正确分流；不确定必先问、明确定位不漏记、非定位不打扰。
- 追加产出合法诊断树节点（叶必含可达 `./…md` 链接、禁词零命中、标识原样），**校验器必跑且通过**。
- 复用 `resolve-domain`，未复制域逻辑；不碰源码仓；全程 UTF-8 无 `?`/`???`。
- 手动 `add`/`init`、读侧消费仍可用。

## 8. 执行交接（评估通过后）
你拍板 **DA（触发机制）/ DB（门禁默认）/ D1（校验器为核心）/ D5 / D6** 后，二选一：① Subagent-Driven（推荐，逐 Task 派新 subagent + 复核）；② Inline（本会话批执行 + 检查点）。在此之前不动手——本文件先供**评估**。

## 9. 自查表（已过一遍）
- **覆盖新需求**：自启动 → DA + Task 6；"不确定先问用户" → DB + Task 6 Step 4 + Task 8 Step 3；文档形态更新 → 第 2 节树 schema + Task 2/5/7；"关联其他 wiki 不自记录" → Task 5 Step 2 + 薄约束。
- **无占位**：树 schema/节点规则/hook 判定逻辑/reason 文本/settings 片段结构均给了具体内容；未展开处（第 6 节升级位）显式标注"评估后展开"。
- **一致性**：`QUICKREF`/`DOC_ROOT`/`resolve-domain`/marker 命名统一；文档 schema 单一来源（第 2 节）。
- **已知留白（需你定）**：DA（布防式 vs 无条件问一次 vs 扫 transcript）、DB（记/问默认松紧）、D5（名）、D6（改 ignore-globs 契约 + 改 settings.json 均需你同意）。
- **诚实边界**：布防式只覆盖"读过速查/用过诊断 skill"的 session；全新现象靠模型兜底或手动——已在 DA 标注。

**参考**：[Claude Code Hooks reference](https://code.claude.com/docs/en/hooks)（`Stop` 的 `decision:block`+`reason`、`stop_hook_active`、`SessionEnd` 仅清理）。
