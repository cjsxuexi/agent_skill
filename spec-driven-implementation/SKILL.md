---
name: spec-driven-implementation
description: Use when turning a business requirement (PRD/spec/Jira issue/Confluence page/docx/mhtml) into working code, especially when the requirement crosses modules or repos, depends on external libraries or data sources, conflicts with existing docs, contains embedded images/PDF/screenshots, or evolves while being implemented. Triggers on field-mapping tasks, cross-service data flow work, Kafka/message-format updates, and "spec says X but code says Y" disagreements.
---

# Spec-Driven Implementation

A staged SOP for taking an ambiguous business requirement through to verified working code. Derived from empirical analysis of 6 real Claude sessions on one project (330 atomic findings, 6 documented self-corrections). **Every checkpoint below was added because a real session failed without it.**

## Core Principle

**All 6 documented self-corrections came from stopping at a local/secondary source — not from reasoning errors.**

Reasoning was almost always sound. What failed was the *evidence chain*: reading one module's constants instead of shared constants; trusting an AI-generated spec instead of the original PRD; parsing `.mhtml` as text instead of extracting embedded images; grepping local Java instead of unpacking the external jar's proto.

**This skill enforces one discipline: trace each fact to its authoritative source before acting on it.** The 6 stages and 8 checkpoints are scaffolding around that single discipline.

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
| **3. 计划** | `superpowers:writing-plans` skill (**path override**: write the plan to `D:\wiki\<wiki-folder>\spec\<task-folder>\implement.md`, NOT writing-plans' default `docs/superpowers/plans/YYYY-MM-DD-*.md` — writing-plans explicitly allows user-preference overrides); plan-mode; `ExitPlanMode` | `implement.md` — Step-by-step plan (context / facts / decisions / files / verify / risks). **Top of file MUST cite `.analysis.md` by absolute path** as `> 分析文档：D:\wiki\<wiki-folder>\spec\<task-folder>\.analysis.md`; do NOT repeat evidence already in `.analysis.md`, only cite its conclusions | Plan approval gate |
| **4. 实现 + 验证** | Dispatch code agent via `superpowers:subagent-driven-development` (preferred — same session, includes implementer + spec reviewer + code quality reviewer three-stage; template in `subagent-driven-development/implementer-prompt.md`); fall back to `superpowers:executing-plans` when subagents aren't desired. **Dispatch prompt's Context section MUST include both absolute paths**: (i) `implement.md` (primary task carrier); (ii) `.analysis.md` (decision/evidence drill-down). Code agent MUST: **not re-decide what is already pinned in `.analysis.md`**; on ambiguity not covered by either doc → return BLOCKED to main agent, do not self-fallback. Inside each task: TDD for logic; offline compile if remote build is restricted; code-graph impact (before) + detect_changes (after) | Tested implementation | — |
| **5. 回写闭环** | Edit spec + project memory; Grep stale-term sweep across all carriers; **sync `.analysis.md`** — any fact discovered during implementation that disagrees with the analysis conclusion (e.g. field ultimately read from A not B) MUST be written back to the corresponding row in `.analysis.md`; **if implementation deviated from plan, sync `implement.md` per the "implement.md 生命周期" section below** | Spec / memory / requirements / discussion docs + `.analysis.md` + `implement.md` all consistent with the final implementation; remaining work bucketed into 待联调 / 待确认 | — |

## 8 Non-Skippable Checkpoints

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
| "implement.md 已生成了，实现过程中改 task 顺序没必要回写文件" | 出现偏离 = 触发 "implement.md 生命周期"。改 `implement.md` 对应章节 + `.analysis.md` 同步记录偏离原因。否则 6 个月后回看会以为 plan 跑通了实际并没有 |

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
    .analysis.md     ← WHY + 决策证据（Stage 2 产出，默认必须生成）
    implement.md     ← HOW + bite-sized tasks（Stage 3 产出，覆盖 writing-plans 默认路径）
```

- **`<wiki-folder>`**：复用现有 wiki 别名规则。源仓库 basename 通常一致（如 `D:\code\fms-server` → `D:\wiki\fms-server`），可被别名（如 `D:\code\fabusurfer` → `D:\wiki\fms-fabusurfer`）。`ls D:\wiki\` 可查。
- **`<task-folder>`**：默认由 code agent 用 PRD 标题 / 任务关键词梳理出小写连字符名（如 `kafka-vehicle-data-report`、`add-data-source-column`、`relocate-meishan-task`）；用户已经命名则沿用；agent 拿不准 → 在写 `.analysis.md` 之前用 `AskUserQuestion` 让用户拍板文件夹名。
- **`.analysis.md`** 文件名按字面（带前导点，符合用户约定）；**`implement.md`** 文件名不带点。
- **wiki 根不存在时**：本 skill 直接创建 `D:\wiki\<wiki-folder>\spec\<task-folder>\` 完整路径（不依赖 `document-systems` 必须先初始化过架构 wiki）。如果 `D:\wiki\` 本身不是 git work tree，按 `document-systems` 的方式 `git init` 一次。
- **git 跟踪**：`spec\` 是 wiki-folder 下的兄弟目录（与 `<module>/` 平级），不被 `document-systems` 写入的 `.gitignore` 模式（当前只忽略 `<DOC_REL>/.review.md`）匹配；两文档默认随 wiki 仓正常 commit / diff。
