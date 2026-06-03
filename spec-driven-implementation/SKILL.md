---
name: spec-driven-implementation
description: Use when turning a business requirement (PRD/spec/Jira issue/Confluence page/docx/mhtml) into working code, especially when the requirement crosses modules or repos, depends on external libraries or data sources, conflicts with existing docs, contains embedded images/PDF/screenshots, or evolves while being implemented. Triggers on field-mapping tasks, cross-service data flow work, Kafka/message-format updates, and "spec says X but code says Y" disagreements.
---

# Spec-Driven Implementation

A staged SOP for taking an ambiguous business requirement through to verified working code. Derived from empirical analysis of 6 real Claude sessions on one project (330 atomic findings, 6 documented self-corrections). **Every checkpoint below was added because a real session failed without it.**

## Core Principle

**All 6 documented self-corrections came from stopping at a local/secondary source — not from reasoning errors.**

Reasoning was almost always sound. What failed was the *evidence chain*: reading one module's constants instead of shared constants; trusting an AI-generated spec instead of the original PRD; parsing `.mhtml` as text instead of extracting embedded images; grepping local Java instead of unpacking the external jar's proto.

**This skill enforces one discipline: trace each fact to its authoritative source before acting on it.** The 6 stages and 9 checkpoints are scaffolding around that single discipline.

**Violating the letter of the checkpoints is violating the spirit. There are no "this one is obvious" exemptions.**

## When to Use

- A business requirement that touches multiple modules / services / repos
- The requirement names data sources, fields, or formats that may live in code, config, shared constants, external jars, or specs — and you don't yet know which is authoritative
- The requirement source is a PRD / spec / Confluence page / docx / mhtml that may contain images or attachments
- Existing docs may conflict with live code (AI-generated specs especially)
- The task spans "understand requirement → design → implement → verify → write back to docs"

## The 6-Stage SOP

| Stage | Use | Produce | Stop point |
|--|--|--|--|
| **0. 需求锚定** | Authoritative source (PRD > spec > code); extract images if mhtml/docx/截图 | Field/scope list split into 业务待确认 vs 内部工程项 | Scope, phasing, cross-project impact → ask user |
| **1. 证据查证** | Subagents (Explore fan-out) + code-graph tool (call-graph/impact) + Grep (field-level取证) | Field→code-location map; every fact traced to its authoritative source | — |
| **2. 决策锁定** | AskUserQuestion: **first open clarify, then closed options with recommendations** for decisions that **materially change the artifact** (e.g. data source choice / topic name / field range / deployment guard / phased-vs-all-at-once scope) | **`D:\wiki\<wiki-folder>\spec\<task-folder>\.analysis.md`** (需求分析设计文档): ① 需求源锚定 (PRD 路径 / 版本 / 锚定日期 / 含图源处理) ② 字段/范围清单 (业务待确认 vs 内部工程项) ③ Stage 1 证据查证表 (字段 → 落点 → 验证方法 → 证据/SHA) ④ 外部源依赖追溯 (jar / proto / 单位 / 坐标系) ⑤ 决策清单 (决策 → 选项 → 选择 → 理由) ⑥ 待联调 / 待确认 | AskUserQuestion locks decisions; **also evaluate whether `.analysis.md` can be skipped — if you think yes, you MUST ask the user to confirm (see CP-分析文档跳过)** |
| **3. 计划** | `superpowers:writing-plans` skill (**path override**: write the plan to `D:\wiki\<wiki-folder>\spec\<task-folder>\implement.md`, NOT writing-plans' default `docs/superpowers/plans/YYYY-MM-DD-*.md` — writing-plans explicitly allows user-preference overrides); plan-mode; `ExitPlanMode` | `implement.md` — Step-by-step plan (context / facts / decisions / files / verify / risks). **Top of file MUST cite `.analysis.md` by absolute path** as `> 分析文档：D:\wiki\<wiki-folder>\spec\<task-folder>\.analysis.md`; do NOT repeat evidence already in `.analysis.md`, only cite its conclusions；**altitude override**：task 写到接口契约 + 注意事项 + 具体测试用例粒度，不贴完整生产/测试代码 body（见下方 "implement.md 任务粒度" 小节） | Plan approval gate |
| **4. 实现 + 验证** | Dispatch code agent via `superpowers:subagent-driven-development` (preferred — same session, includes implementer + spec reviewer + code quality reviewer three-stage; template in `subagent-driven-development/implementer-prompt.md`); fall back to `superpowers:executing-plans` when subagents aren't desired. **Dispatch prompt's Context section MUST include both absolute paths**: (i) `implement.md` (primary task carrier); (ii) `.analysis.md` (decision/evidence drill-down). Code agent MUST: **not re-decide what is already pinned in `.analysis.md`**; on ambiguity not covered by either doc → return BLOCKED to main agent, do not self-fallback. Inside each task: TDD for logic; offline compile if remote build is restricted; code-graph impact (before) + detect_changes (after) | Tested implementation | — |
| **5. 回写闭环** | Edit spec + project memory; Grep stale-term sweep across all carriers; **sync `.analysis.md`** — any fact discovered during implementation that disagrees with the analysis conclusion (e.g. field ultimately read from A not B) MUST be written back to the corresponding row in `.analysis.md`; **if implementation deviated from plan, sync `implement.md` per the "implement.md 生命周期" section below** | Spec / memory / requirements / discussion docs + `.analysis.md` + `implement.md` all consistent with the final implementation; remaining work bucketed into 待联调 / 待确认 | — |

## 9 Non-Skippable Checkpoints

Each prevents a specific documented failure mode. When you reach the trigger, **stop and run the action before continuing**.

| CP | Trigger | Action | Prevents |
|--|--|--|--|
| **CP-0 环境前置** | Working on Windows with Chinese paths/files/content (or other CJK env) | Invoke the platform shell-safety skill first (e.g., `windows-cn-shell-safety`) | Bash backslash吞噬, GBK 乱码, `find` / `$null` 不适配 (the recurring "噪声税") |
| **CP-需求最新性** | Stage 0, before reading any spec | Confirm spec/PRD is the latest version; explicitly ask the user: "Is there any new requirement you have that hasn't yet made it into the docs?" | Building from a stale plan (real: v1 plan written from old spec, rejected by user) |
| **CP-含图源抽图** | Stage 0, requirement source is mhtml / docx / PDF / 截图 / Confluence page with images | Extract embedded images and **visually read each one** (Read tool reads PNG/JPG directly); never rely on pure text parse alone. **Minimal extraction recipes**: `.mhtml` → Python `email.parser`, iterate parts, save `Content-Type: image/*` parts; `.docx` → `zipfile`, extract `word/media/*`; `.pdf` → Read tool with `pages=` | Missing 4 fields whose definitions exist only in screenshots |
| **CP-数据源双验** | Stage 1, about to conclude "data X is in source Y" | Cross-verify via at least **two of**: (a) **shared/cross-module constants library** — find it by scanning `pom.xml` / `build.gradle` for `*-common-*` / `*-protocol-*` / `*-api` / `*-sdk` dependencies, or modules whose names contain `constants` / `keys` / `protocol`; (b) code-graph read/write relations for the entity; (c) full-repo key-name Grep across **all naming variants** (snake_case / camelCase / SCREAMING_SNAKE / 中文 alias) | MongoDB-vs-Redis misjudgment from reading only one module's constants subset |
| **CP-外部源追踪** | Stage 1, a field reference points to an external dependency (jar / proto / library) | Unpack the jar / read the proto / check the library source; **do NOT conclude "no source" from in-repo grep alone**. Unit/coord-system uncertainties: read source or ask domain expert. **Minimal jar-unpack on Windows**: `jar xf foo.jar` if JDK on PATH, else PowerShell `[System.IO.Compression.ZipFile]::ExtractToDirectory('foo.jar','out')`, or 7-Zip `7z x foo.jar -oout`. After extract: `grep -r 'field_name' out/` and check `*.proto` directly | Acceleration field declared "missing" when it was actually in an external grpc-api jar; sign-convention assumed wrong |
| **CP-子代理护栏** | Stage 1, **dispatching any Explore / Plan subagent** | The dispatch prompt MUST explicitly tell the subagent: (a) use the code-graph tool for call-graph/impact, not just Grep; (b) read the module's architecture wiki first if present — `document-systems` writes it at `D:\wiki\<wiki-folder>\<module>\architecture.md` (or `D:\wiki\<wiki-folder>\architecture.md` for single-system repos); `<wiki-folder>` usually matches the source repo basename but may be aliased (e.g. source `D:\code\fabusurfer` → wiki `D:\wiki\fms-fabusurfer`); `ls D:\wiki\` if unsure; (c) **do NOT report a field or list you haven't actually Read**; (d) mark every inference with "(推测)" | Subagents fabricating field/column names from class names alone, returning them as facts |
| **CP-code-graph影响面** | Stage 4, before AND after a code change | Run `impact(target, direction:"upstream", repo:"<repo>")` before; `detect_changes(repo, scope:"all")` after. **Index lag caveat**: for code you just wrote (uncommitted), `impact` returns not-found and `detect_changes` returns 0 — that means "pure addition, LOW risk to existing code", NOT "no impact / unknown". Still need human/compile verification of the new code itself. | Forgetting impact analysis; misreading 0-change as 0-information |
| **CP-分析文档跳过** | End of Stage 2, about to enter Stage 3 | **Default = generate `.analysis.md`**. If you (the agent) judge that this task does not need one (e.g. single-file change / pure rename / comment or config tweak — AND it does NOT touch data flow / external dependencies / cross-module / image-bearing spec source), **you MUST use `AskUserQuestion` to list ≥ 2 concrete reasons and let the user decide**. Until the user explicitly agrees, you must generate it | "Agent quietly skips `.analysis.md` → Stages 0-2 discipline decouples → repeats C-01~C-05 (all 6 documented self-corrections live in the analysis half)". The skip decision cannot be made unilaterally by the agent |
| **CP-分析文档实质** | Stage 2 正在写 `.analysis.md`；或 Stage 3 正要把"证据查证表 / 影响面 / 决策(选项·选择·理由) / file:line 落点"写进 `implement.md` | `.analysis.md` 必须含真实的 ③证据查证表（字段 → 落点 file:line/SHA → 验证方法 → 证据）与 ⑤决策清单（决策 → 选项 → 选择 → 理由）；**通篇复述需求 = 失败**（那是"需求复述"不是"分析设计"）。材料级决策（数据源 / topic / 字段范围 / 部署 guard / 分期 scope）必须先 `AskUserQuestion` 锁定再写入 ⑤，**不准以"推荐"形态躺在 `implement.md`**。证据/决策只在 `.analysis.md` 落地，`implement.md` 引用结论 | `.analysis.md` 空壳化 → `implement.md` 反背 Code Evidence/Impact/Design Decision（双重臃肿）；数据源等关键决策被 plan 悄悄拍板、两次生成 scope 打架 |

## Common Rationalizations (close them BEFORE you act)

| Excuse | Reality |
|--|--|
| "The spec in `document/` is the authoritative source" | Many `document/spec/` files are AI-generated. User has explicitly said they're "不一定准". Treat as **starting point**, verify against code. Conflict → code wins. |
| "I read the relevant constants file, the data isn't there" | You read **one module's** constants. Check shared/cross-module constants + full-repo key grep before concluding. |
| "It's a `.mhtml`, I'll grep the text" | Required fields are often in **embedded images**. Extract them. |
| "Grep is faster than the code-graph tool" | For field-level取证, yes; for call-graph / impact / read-write relations, the code-graph tool is what it exists for. CLAUDE.md may even mandate it — and "I read the mandate and still grepped" is a documented failure mode. |
| "I'll write the plan myself, `writing-plans` skill is overkill" | Same content; the skill is the流程门禁. Use it. |
| "The subagent will figure it out" | Subagents inherit your blind spots and **amplify** them. Pass methodology expectations in the prompt — see CP-子代理护栏. |
| "I just need to grep this one field" | If the field touches data flow / dependency / impact → CP-数据源双验 / CP-code-graph影响面 still apply. |
| "It's just a small/obvious change, impact analysis is overkill" | Documented case: "small obvious change" turned out to break a downstream caller. The check costs 30 seconds. |
| "0 changes from detect_changes means nothing to verify" | It means "pure addition, no existing code affected". The NEW code still needs its own verification (compile + tests). |
| "这次很简单 / 字段都明确了 / 一行改动，不用写 `.analysis.md`" | 默认必须生成。想跳过 → 触发 CP-分析文档跳过 → `AskUserQuestion` 列 ≥2 条理由请用户批准。agent 不能单方面决定 |
| "`.analysis.md` 我写了啊（其实是把需求复述了一遍）" | 复述需求 ≠ 分析设计。Stage 2 的实质是 ③证据查证表 + ⑤决策清单；缺了它们，`implement.md` 必然反背 Code Evidence/Design Decision、材料级决策被 plan 悄悄拍板（CP-分析文档实质） |
| "implement.md 已生成了，实现过程中改 task 顺序没必要回写文件" | 出现偏离 = 触发 "implement.md 生命周期"。改 `implement.md` 对应章节 + `.analysis.md` 同步记录偏离原因。否则 6 个月后回看会以为 plan 跑通了实际并没有 |
| "`writing-plans` 要求每步贴完整代码，我照贴就行" | Stage 4 消费者是 capable code agent + spec/质量双 reviewer + 测试，不是 `writing-plans` 假设的弱执行者。预写的生产/测试 body 多是 planner 猜签名的 fiction，实现者读真实文件仍要 reconcile。写到接口契约 + 具体测试用例即可；但砍 body **不等于**松 No-Placeholders，空话照旧禁止（见 "implement.md 任务粒度"） |

## Red Flags — STOP and Re-check

- About to conclude "X is in Y" after reading **one** source → CP-数据源双验
- About to grep `<field>` in repo, get 0 hits, conclude "no source" → CP-外部源追踪
- About to dispatch a subagent with just "explore X" or "find Y" → CP-子代理护栏
- About to write a multi-step plan in prose without invoking `writing-plans` → use the skill
- About to make code changes you "know are safe" without code-graph impact → CP-code-graph影响面
- Hit `UnicodeEncodeError` / `Unrecognized escape \U` / `cd: D:codefabusurfer` → CP-0 + invoke `windows-cn-shell-safety`
- About to mark a unit as "radians" / "km/h" / a sign as "forward" without source evidence → CP-外部源追踪
- About to skip Stage 5 because "the code works" → docs/memory will drift, future sessions will pay
- `detect_changes` reports **0 changed flows** for code you just wrote → that means "pure addition, LOW risk to existing code", **not** "no impact / nothing to verify" — the new code still needs its own compile + tests
- Long session crossing days / topics → re-trigger CP-需求最新性 ("any new requirement since last check?")
- About to start Stage 3 (writing `implement.md`) without `.analysis.md` 存在、且用户没明确授权跳过 → CP-分析文档跳过
- 实施过程出现"加 task / 改顺序 / 漏步骤" 但 `implement.md` 没改 → 见 "implement.md 生命周期" 小节、同步两文档
- implement.md 某个 task 贴了完整生产函数 body / 完整测试类 boilerplate → 停，降到接口契约 + 具体测试用例（见 "implement.md 任务粒度"）；省下的篇幅换成更精确的契约，不是 prose 含糊
- `.analysis.md` 通篇是需求复述、没有 ③证据查证表 / ⑤决策清单 → 它是空壳，Stage 2 实际没做（CP-分析文档实质）；补实质再进 Stage 3
- 数据源 / 分期 scope 这类材料级决策以"推荐"出现在 `implement.md`、而非 `AskUserQuestion` 锁进 `.analysis.md` ⑤ → plan 替用户拍板了，停下走 AskUserQuestion

## .analysis.md 必须有实质（证据表 + 决策清单，不是需求复述）

观察到的失败：agent 把 `.analysis.md` 写成"需求复述"（甚至标题写成"需求文档"），把真正的证据/决策塞进 `implement.md`，于是 `.analysis.md` 空壳、`implement.md` 既背设计又背计划。

**`.analysis.md` 是"分析设计"不是"需求拷贝"。通篇复述需求 = Stage 2 没做。** 证据与决策**只在 `.analysis.md` 落地**，`implement.md` 引用其结论：

| 内容 | 落地处 | implement.md 怎么写 |
|--|--|--|
| 字段/接口的代码落点（file:line / SHA） | `.analysis.md` ③证据查证表 | "落点见分析文档 ③" 一句带过 |
| code-graph 影响面 | `.analysis.md` ④ | task 只写"该改动 impact=HIGH，见 ④"+ 对应护栏 |
| 材料级决策（数据源 / topic / 范围 / 分期 scope） | `.analysis.md` ⑤决策清单（先 `AskUserQuestion` 锁定） | "采用方案见 ⑤决策#N"，不重述理由 |

③ 行示例（每个待查字段一行，带真实证据）：
`| available | Equipment.java:56 @TableField(exist=false) 默认 true | Read+Grep | 已读源码 |`

⑤ 行示例（材料级决策先问用户再落）：
`| 占用持久化源 | Oracle 表 / Redis / 混合 | Oracle 表 PARKING_LOT_OCCUPANCY | 跨接口+事件+扫描共享、需重启存活与审计 |`

**材料级决策不准以"推荐"形态躺在 `implement.md`**——那等于 plan 替用户拍板。走 `AskUserQuestion`（先开放澄清、再带推荐的封闭选项），锁定后写入 ⑤，`implement.md` 只引用编号/标题。

## implement.md 任务粒度（写到契约+用例，不贴完整 code body）

Stage 3 借 `writing-plans` 的骨架（header / File Structure / task 分解 / Self-Review / No-Placeholders），但**覆盖它"每步贴完整代码"的默认**。理由：Stage 4 的消费者不是 `writing-plans` 假设的"几乎不懂工具链、不太会写测试"的弱执行者，而是 capable code agent——自带 TDD、能 Read 真实代码、跑 code-graph，后面还接 spec reviewer + code-quality reviewer + 测试三道闸。预写的生产/测试 body 多半是 planner 猜签名的 fiction，实现者打开真实文件仍要 reconcile；贴它省得少、把 wiki 仓刷成 stale 代码、还淹没真正高价值的决策与注意事项。

**每个 task 写到"有能力的实现者能无歧义动手"为止：**

| 保留（推导成本高 / 本身是决策） | 砍掉（实现者能机械产出） |
|--|--|
| 链路 + 文件结构：改哪些文件、各自职责、task 顺序、新增依赖 | 生产函数的完整 body |
| 接口契约：确切的方法/字段/topic/enum 名与签名、`.analysis.md` 钉死的取值（数据源 / 状态集 / 单位符号 / 字段范围） | 能从契约直接推出的 import / 依赖注入 / 样板 |
| 注意事项：坑（并发 / 迁移 / 单位约定 / 为何排除某状态）、code-graph impact 的期望值 | 完整测试类的框架 boilerplate |
| **具体测试用例**：每个 case 的 input → expected、边界、哪个必须先 fail、验证命令与期望输出 | — |
| "确切形态本身即决策"的非平凡片段：一段 regex、一处 proto 字段映射、一个微妙并发 guard → 照贴 | — |

**判据一句话**：确切代码形态本身是决策 → 贴；纯机械转写 → 只给契约，让实现者写。

**红线（别把"砍 body"做成"打哈哈"）**：这不是放松 `writing-plans` 的 No-Placeholders。"加适当的错误处理 / 处理边界情况 / 给上面补测试"这类空话照旧是 plan failure。砍掉 body 的位置必须换成**更精确的契约 + 更具体的用例**，不是 prose 含糊——测试用例尤其要具体到 input→expected，测试设计是 spec，不能甩给实现者拍脑袋。

## implement.md 生命周期

**默认快照、偏离时更新**：`implement.md` 在 Stage 3 一次性生成为准。Stage 4 实施进度走 TodoWrite（内存）；**默认不动 `implement.md` 文件**，避免 wiki 仓被每个 task 的 checkbox 改动刷成噪声 commit。

**触发更新的情况**（出现以下任一就要改）：

- 追加了 plan 没列出的 task（如发现需要额外的 schema 迁移）
- 改了 task 顺序（依赖关系发现错位）
- 临时插入的随手事项（需要补一个 helper / 调一行配置）
- 验证阶段发现 plan 步骤有遗漏

**更新动作**：直接 Edit `implement.md` 对应章节；**同步在 `.analysis.md` 的"待联调 / 待确认"或"决策清单"中追加一行说明偏离原因**，保持两文档前后一致。

## 任务目录与文件命名

```
D:\wiki\<wiki-folder>\spec\<task-folder>\
    .analysis.md     ← WHY + 证据查证表 + 决策清单（分析设计，非需求复述；Stage 2 产出，默认必须生成）
    implement.md     ← HOW + bite-sized tasks（接口契约+测试用例粒度，非完整 code body；Stage 3 产出，覆盖 writing-plans 默认路径）
```

- **`<wiki-folder>`**：复用现有 wiki 别名规则。源仓库 basename 通常一致（如 `D:\code\fms-server` → `D:\wiki\fms-server`），可被别名（如 `D:\code\fabusurfer` → `D:\wiki\fms-fabusurfer`）。`ls D:\wiki\` 可查。
- **`<task-folder>`**：默认由 code agent 用 PRD 标题 / 任务关键词梳理出小写连字符名（如 `kafka-vehicle-data-report`、`add-data-source-column`、`relocate-meishan-task`）；用户已经命名则沿用；agent 拿不准 → 在写 `.analysis.md` 之前用 `AskUserQuestion` 让用户拍板文件夹名。
- **`.analysis.md`** 文件名按字面（带前导点，符合用户约定）；**`implement.md`** 文件名不带点。
- **wiki 根不存在时**：本 skill 直接创建 `D:\wiki\<wiki-folder>\spec\<task-folder>\` 完整路径（不依赖 `document-systems` 必须先初始化过架构 wiki）。如果 `D:\wiki\` 本身不是 git work tree，按 `document-systems` 的方式 `git init` 一次。
- **git 跟踪**：`spec\` 是 wiki-folder 下的兄弟目录（与 `<module>/` 平级），不被 `document-systems` 写入的 `.gitignore` 模式（当前只忽略 `<DOC_REL>/.review.md`）匹配；两文档默认随 wiki 仓正常 commit / diff。
