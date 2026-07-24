---
name: spec-driven-implementation
description: Use when turning a business requirement (PRD/spec/ONES or Jira issue/Confluence page/docx/mhtml) into working code, especially when the requirement crosses modules or repos, depends on external libraries or data sources, conflicts with existing docs, contains embedded images/PDF/screenshots, or evolves while being implemented. Triggers on field-mapping tasks, cross-service data flow work, Kafka/message-format updates, and "spec says X but code says Y" disagreements.
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
| **0. 需求锚定** | Authoritative source (PRD > spec > code); extract images if mhtml/docx/截图；人提供 ONES 单号时先通过 `ones-mcp` 读取详情 | Field/scope list split into 业务待确认 vs 内部工程项；记录 ONES 单号与已取回的需求事实 | Scope, phasing, cross-project impact → ask user |
| **1. 证据查证** | Subagents (Explore fan-out) + code-graph tool (call-graph/impact) + Grep (field-level取证) | Field→code-location map; every fact traced to its authoritative source | — |
| **2. 决策锁定** | AskUserQuestion: **first open clarify, then closed options with recommendations** for decisions that **materially change the artifact** (e.g. data source choice / topic name / field range / deployment guard / phased-vs-all-at-once scope) | **分析载体**（先续写已锚定载体，新任务才按配置选择；见「分析载体与配置」章）：默认六块齐全——①需求源锚定 ②字段/范围清单 ③证据查证表 ④外部源依赖追溯 ⑤决策清单 ⑥待联调/待确认；无适用内容写「无 + 查证依据」。顶部记录 `ONES 单号`，未提供写「未提供」。issue 模式另有版本 marker、首次原始需求快照与关联；多 issue 时主 issue 必须汇总子 issue 索引及最终 ⑤ | 在开始产出或省略任何分析小节之前判断是否请求简化；想简化必须先走 CP-分析简化审批，用户批准前按全量六块执行 |
| **3. 计划** | `superpowers:writing-plans` skill (**path override**: write to `D:\wiki\<wiki-folder>\spec\<task-folder>\implement.md`); plan-mode; `ExitPlanMode`. 先从分析载体取得稳定 `implementation_key`，在精确 wiki repo 的全部 `spec\*\implement.md` 头部查重：一份则复用，零份才创建，多份或引用冲突则 BLOCKED | `implement.md` — Step-by-step plan (context / facts / decisions / files / verify / risks)。顶部必须连续写 `> Implementation key: ...` 与 `> ONES 单号: ...`（未提供写「未提供」）。wiki 模式另引 `analysis.md` 绝对路径；issue 模式写主分析 issue 与全量子 issue 的人读标识/标题，不拼 uuid 或读取命令。主 issue ⑤未收敛不得生成计划；task 粒度见下节 | Plan approval gate |
| **4. 实现 + 验证** | Dispatch via `superpowers:subagent-driven-development` (preferred) or `superpowers:executing-plans`. Context 分模式：wiki 模式带 `implement.md` + `analysis.md` 两个绝对路径；issue 模式带 implement 路径、主 issue + 全量子 issue 标识及逐个 `multica issue get LOC-n --output json` 命令，并内联主 issue 汇总后的 ⑤全文。不得重决分析载体已锁定的决策；任一必要 issue 取不到且内联不足，或主/子 ⑤冲突 → BLOCKED。Inside each task: TDD; offline compile if needed; code-graph impact (before) + detect_changes (after) | Tested implementation | — |
| **5. 回写闭环** | Edit spec + project memory; Grep stale-term sweep。按变化类型回写：分析事实/决策变 → 同步分析载体并加修订行；task/顺序/实现契约变 → 同步 `implement.md` 正文；两者都变 → 两者；ONES 单号后补/更正/撤销 → 按例外规则同步两处；纯过程输出且未改变二者 → 不复制进载体。保留空 `## 执行记录`，本次不自动填行。Multica issue run 仍用 `--content-file` 发布一条简洁最终结果评论（outcome、PR/commit、测试摘要、implement.md 指针） | Spec / memory / requirements / 分析载体 / `implement.md` 与最终实现一致；remaining work bucketed into 待联调 / 待确认 | — |

## 10 Non-Skippable Checkpoints

Each prevents a specific documented failure mode. When you reach the trigger, **stop and run the action before continuing**.

| CP | Trigger | Action | Prevents |
|--|--|--|--|
| **CP-0 环境前置** | Working on Windows with Chinese paths/files/content (or other CJK env) | Invoke the platform shell-safety skill first (e.g., `windows-cn-shell-safety`) | Bash backslash吞噬, GBK 乱码, `find` / `$null` 不适配 (the recurring "噪声税") |
| **CP-需求最新性** | Stage 0, before reading any spec | Confirm spec/PRD is the latest version; explicitly ask the user: "Is there any new requirement you have that hasn't yet made it into the docs?" | Building from a stale plan (real: v1 plan written from old spec, rejected by user) |
| **CP-ONES详情补全** | 人明确提供一个或多个 ONES 单号/链接时；包括分析或计划生成后才补充 | 立即执行「可选 ONES 单号与详情」流程：用当前宿主实际暴露的 `ones-mcp` 只读能力取得每张单的详情；单号同步进分析载体与 `implement.md`，相关事实只落分析载体，计划引用已锁定结论。未成功取详时不得声称已补全 | 只抄单号、不读需求详情，或两处追溯字段漂移 |
| **CP-含图源抽图** | Stage 0, requirement source is mhtml / docx / PDF / 截图 / Confluence page with images | Extract embedded images and **visually read each one** (Read tool reads PNG/JPG directly); never rely on pure text parse alone. **Minimal extraction recipes**: `.mhtml` → Python `email.parser`, iterate parts, save `Content-Type: image/*` parts; `.docx` → `zipfile`, extract `word/media/*`; `.pdf` → Read tool with `pages=` | Missing 4 fields whose definitions exist only in screenshots |
| **CP-数据源双验** | Stage 1, about to conclude "data X is in source Y" | Cross-verify via at least **two of**: (a) **shared/cross-module constants library** — find it by scanning `pom.xml` / `build.gradle` for `*-common-*` / `*-protocol-*` / `*-api` / `*-sdk` dependencies, or modules whose names contain `constants` / `keys` / `protocol`; (b) code-graph read/write relations for the entity; (c) full-repo key-name Grep across **all naming variants** (snake_case / camelCase / SCREAMING_SNAKE / 中文 alias) | MongoDB-vs-Redis misjudgment from reading only one module's constants subset |
| **CP-外部源追踪** | Stage 1, a field reference points to an external dependency (jar / proto / library) | Unpack the jar / read the proto / check the library source; **do NOT conclude "no source" from in-repo grep alone**. Unit/coord-system uncertainties: read source or ask domain expert. **Minimal jar-unpack on Windows**: `jar xf foo.jar` if JDK on PATH, else PowerShell `[System.IO.Compression.ZipFile]::ExtractToDirectory('foo.jar','out')`, or 7-Zip `7z x foo.jar -oout`. After extract: `grep -r 'field_name' out/` and check `*.proto` directly | Acceleration field declared "missing" when it was actually in an external grpc-api jar; sign-convention assumed wrong |
| **CP-子代理护栏** | Stage 1, **dispatching any Explore / Plan subagent** | The dispatch prompt MUST explicitly tell the subagent: (a) use the code-graph tool for call-graph/impact, not just Grep; (b) read the module's architecture wiki first if present — `document-systems` writes it at `D:\wiki\<wiki-folder>\<module>\architecture.md` (or `D:\wiki\<wiki-folder>\architecture.md` for single-system repos); `<wiki-folder>` usually matches the source repo basename but may be aliased (e.g. source `D:\code\fabusurfer` → wiki `D:\wiki\fms-fabusurfer`); `ls D:\wiki\` if unsure; (c) **do NOT report a field or list you haven't actually Read**; (d) mark every inference with "(推测)" | Subagents fabricating field/column names from class names alone, returning them as facts |
| **CP-code-graph影响面** | Stage 4, before AND after a code change | Run `impact(target, direction:"upstream", repo:"<repo>")` before; `detect_changes(repo, scope:"all")` after. **Index lag caveat**: for code you just wrote (uncommitted), `impact` returns not-found and `detect_changes` returns 0 — that means "pure addition, LOW risk to existing code", NOT "no impact / unknown". Still need human/compile verification of the new code itself. | Forgetting impact analysis; misreading 0-change as 0-information |
| **CP-分析简化审批** | Stage 2 开始写分析载体前；或写作中首次准备省略/瘦身小节之前 | **Default = ①-⑥ 六块齐全**，无适用内容写「无 + 查证依据」。若 agent 判断可简化（单文件/纯重命名/注释或配置微调，且不碰数据流/外部依赖/跨模块/含图源），必须在省略前用 `AskUserQuestion` 列 ≥2 个具体理由，并让用户明确批准可省略的①②④⑥范围；③证据查证表与⑤决策清单不可省略。未获明确答复则按全量版，无法继续则 BLOCKED | 防止先简化后补审批；issue 只剩原始需求 / `analysis.md` 空壳均属变相跳过；简化决定不能由 agent 单方面作出 |
| **CP-分析实质** | Stage 2 正在写分析载体；多 issue 汇总完成前；或 Stage 3 正要把证据/决策写进 `implement.md` | 每个分析单元都须有真实 ③证据查证表与⑤决策清单；主分析 issue 还必须列全量子 issue 并汇总无冲突的最终 ⑤。**通篇复述需求 = 失败**。材料级决策必须先 AskUserQuestion 锁定再落⑤，不准以“推荐”躺在 `implement.md`。③⑤ 永不因简化审批而消失 | 防空壳、分散决策未收敛、plan 替用户拍板及多 issue scope 打架 |

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
| "这次很简单 / 字段都明确了 / 一行改动，分析可以少写" | 默认六块；想省略①②④⑥须事前走 CP-分析简化审批并获得明确范围，③⑤永不省略。agent 不能先简化后补审批 |
| "分析载体我写了啊（其实是把需求复述了一遍）" | 复述需求 ≠ 分析设计。Stage 2 的实质是 ③证据查证表 + ⑤决策清单；缺了它们，`implement.md` 必然反背 Code Evidence/Design Decision、材料级决策被 plan 悄悄拍板（CP-分析实质） |
| "implement.md 已生成了，实现过程中改 task 顺序没必要回写文件" | 出现偏离 = 触发 "implement.md 生命周期"。plan-only 偏离只更新 `implement.md`；只有同时暴露新的分析事实/决策才同步分析载体，禁止恢复旧式强制双写 |
| "issue 描述太长，证据表就省了吧" | ③⑤ 永不省略；平台拒绝 payload 时 BLOCKED 并报告实际错误，不能用未授权瘦身掩盖。已验证的 10KB+ 样本只证明该样本保真，不证明无平台上限 |
| "配置是 issue 模式但没有 issue，先写个本地文件回头再挪" | 新任务走三分支；已有 issue 载体等待 CLI 恢复。只有用户明确同意才降级，禁止静默制造第二载体 |
| "有几个分析子 issue，implement.md 引主 issue 就够了" | 主 issue 必须列全量子 issue 并汇总最终⑤；`implement.md` 与 Stage 4 都带主/子索引。未收敛或冲突即 BLOCKED |
| "把详细实现步骤/日志贴进 issue，final comment 也一起禁掉" | `implement.md` 是权威，但 Multica final comment 是强制通知：只发 outcome、PR/commit、测试摘要和 implement.md 指针，不复制全文 |
| "config 写成 issues 也按默认 wiki 吧" | 只有文件/键缺失才默认；不可读、非法 JSON、根类型错误、值类型错误、未知值全部 fail closed，避免拼写错误切错载体 |
| "`writing-plans` 要求每步贴完整代码，我照贴就行" | Stage 4 消费者是 capable code agent + spec/质量双 reviewer + 测试，不是 `writing-plans` 假设的弱执行者。预写的生产/测试 body 多是 planner 猜签名的 fiction，实现者读真实文件仍要 reconcile。写到接口契约 + 具体测试用例即可；但砍 body **不等于**松 No-Placeholders，空话照旧禁止（见 "implement.md 任务粒度"） |
| "ONES 单号记进文档就算完成，不必再查" | 人提供单号即触发 `ones-mcp` 详情读取；单号是追溯锚点，不是需求详情的替代品。未提供则不追问、不阻塞、不猜测 |

## Red Flags — STOP and Re-check

- About to conclude "X is in Y" after reading **one** source → CP-数据源双验
- About to grep `<field>` in repo, get 0 hits, conclude "no source" → CP-外部源追踪
- About to dispatch a subagent with just "explore X" or "find Y" → CP-子代理护栏
- About to write a multi-step plan in prose without invoking `writing-plans` → use the skill
- About to make code changes you "know are safe" without code-graph impact → CP-code-graph影响面
- Hit `UnicodeEncodeError` / `Unrecognized escape \U` / `cd: D:codefabusurfer` → CP-0 + invoke `windows-cn-shell-safety`
- About to mark a unit as "radians" / "km/h" / a sign as "forward" without source evidence → CP-外部源追踪
- About to skip Stage 5 because "the code works" → docs/memory will drift, future sessions will pay
- 人已提供 ONES 单号，但准备只抄单号、硬编码某个宿主工具前缀，或把未取回的内容当成 ONES 事实 → CP-ONES详情补全
- `detect_changes` reports **0 changed flows** for code you just wrote → that means "pure addition, LOW risk to existing code", **not** "no impact / nothing to verify" — the new code still needs its own compile + tests
- Long session crossing days / topics → re-trigger CP-需求最新性 ("any new requirement since last check?")
- About to start Stage 3 before the analysis carrier has real ③⑤, or before an approved simplification scope exists → CP-分析简化审批 + CP-分析实质
- 实施过程出现"加 task / 改顺序 / 漏步骤"但 `implement.md` 没改，或准备把 plan-only 偏离强制双写到分析载体 → 按 "implement.md 生命周期" 的 D4 分类处理
- implement.md 某个 task 贴了完整生产函数 body / 完整测试类 boilerplate → 停，降到接口契约 + 具体测试用例（见 "implement.md 任务粒度"）；省下的篇幅换成更精确的契约，不是 prose 含糊
- 分析载体通篇是需求复述、没有 ③证据查证表 / ⑤决策清单 → 它是空壳，Stage 2 实际没做（CP-分析实质）；补实质再进 Stage 3
- 数据源 / 分期 scope 这类材料级决策以"推荐"出现在 `implement.md`、而非 `AskUserQuestion` 锁进分析载体 ⑤ → plan 替用户拍板了，停下走 AskUserQuestion
- issue update 前 marker 缺半/重复/版本未知，或二次 get 的 `description/updated_at` 已变 → 停止覆盖，重新合并或 BLOCKED
- 新任务同时发现新式 wiki marker 与 issue marker，或准备因配置变化切换旧任务载体 → 停，请用户确定权威载体
- 多个分析 issue 尚未由主 issue 汇总最终⑤，或准备只把一个 LOC-n 交给实现者 → 停，先收敛
- 当前 task-folder 已有 `implement.md` 却准备再建一份、同一 `implementation_key` 已有多份 `implement.md`，或 wiki 精确 repo root 不可写 → 停，复用/解决冲突/请求资源，禁止宽根 `git init`
- 准备把详细 task/过程日志写进 issue → 停；但也不得省略 Multica runtime 强制的一条简洁最终结果评论
- 准备往空的「## 执行记录」自动追加行 → 停：本次只预留，writer/格式/里程碑更新由后续方案定义

## 分析载体与配置（analysis.md 的落点由配置决定）

Stage 2 先解析**该任务已锚定的载体**，只有新任务才读取配置选择初始载体。分析实质（①-⑥ 六块）与分析类 checkpoint 在两种模式下完全一致。实现侧不受配置影响：一个实现单元有且仅有一份 `implement.md`；详细实现计划/task/过程日志不复制进 issue，Multica 的一条最终结果评论仅作通知与索引。「## 执行记录」本次只预留空节，未来写入契约另行设计。

### 存储与权限前置

先确认目标 wiki 的**精确 repo root**与 task-folder 对当前 agent 可读写、可提交；`implement.md` 在两种模式下都依赖该持久化位置。Multica runtime 未注入对应 `local_directory` / `github_repo` 资源或 task checkout 时，向用户说明并 BLOCKED；不得擅自新增 project resource，也不得在宽泛的 `D:\wiki` 根执行 `git init`。

### 配置

从本 skill base directory 解析相邻的 `config.json`（随 skill 仓版本管理，不依赖 wiki 根）：

```json
{"analysis_carrier":"wiki"}
```

- 只接受 string `"wiki"|"issue"`。文件不存在或 JSON object 中缺键才默认 `wiki`；文件不可读、JSON 非法、根不是 object、值非 string、未知值一律报配置错误并 AskUserQuestion/BLOCKED，绝不静默回落。
- `"wiki"` → 新任务生成 `analysis.md`，写 v1 analysis carrier marker + `implementation_key` 以区别 legacy 归档；`"issue"` → 新任务把六块分析写入主分析 issue description，wiki 侧仍只新增 `implement.md`。
- 新任务在 Stage 2 首次写载体前读取一次配置并固定本任务选择；配置只影响新任务，workspace 重导入会覆盖运行侧手改。

### 可选 ONES 单号与详情

ONES 单号是**可选、只接受人明确提供**的需求追溯信息，不是第三种 `analysis_carrier`，也不替代 `implementation_key`。两种分析模式执行同一规则：

- **未提供**：不得从 `LOC-n`、分支名、相似字符串或其他系统猜测，不得只为索取单号发问或 BLOCKED；分析载体与 `implement.md` 都写 `> ONES 单号: 未提供` 后继续。
- **已提供**：原样保留人给出的单号及顺序。先在当前宿主发现 `ones-mcp` 实际暴露的只读工具，优先调用逻辑能力 `get_issue_details`；不要把 Claude Code、Codex 等宿主添加的命名空间前缀写死。若详情工具不能直接接收人读单号，先用已暴露的 `get_issue_human_readable_keys` 或 `query_issues_by_onesql` 等只读能力唯一解析目标，再调用详情工具；参数必须以实时 tool schema 为准，不猜字段名。
- **使用详情**：只采用工具实际返回的标题、描述、验收标准、状态、类型、关联资料等字段，把与当前实现有关的事实分别落入 ①-⑥，并在 ① 记录详情获取能力与返回的版本/更新时间（若有）。不要把整段原始 payload 复制进 `implement.md`；计划只保留 ONES 单号和对分析结论的引用。详情引用了评论、附件、页面或图片且它们会影响范围/验收时，继续用相应只读工具查证，并执行 CP-含图源抽图。
- **只读边界**：该流程不授权创建、更新、流转或评论 ONES 工单。工具未暴露、未认证、查询零/多匹配或详情读取失败时，不得绕过 MCP 直连 HTTP，也不得编造补全；在 ⑥ 记录缺口并询问用户。缺失信息会实质改变设计时 BLOCKED，否则仅在用户明确接受该缺口后继续。
- **身份边界**：新 wiki 任务若以 ONES 为唯一/主要需求源，首次锚定时按既有 `source:<规范化需求源锚点+版本>` 规则把初始 ONES 单号与已确认版本纳入 key；若 ONES 只是补充源则不纳入。marker 创建后 key 即为实现单元的冻结身份：后补或纠正追溯字段不改 key；若实际是换成另一个实现单元，不得伪装成“更正”，应 AskUserQuestion 后另行建载体或迁移。
- **后补与变更**：分析或计划生成后人再提供、更正或撤销单号时，重新执行适用的详情读取，并同步分析载体和 `implement.md` 顶部；同时删除、重验或明确标记旧单号导出的事实为已失效，在 quote 头追加修订行，禁止旧事实继续显示为当前结论。长会话重新触发 CP-需求最新性时，若 ONES 是主要需求源或人提示工单已更新，也要重新读取并记录有意义的差异。

### 续写优先级与实现身份

**续写优先于配置，但禁止首个命中即返回。** 先收集全部证据：`implement.md` 头部引用、当前/用户给出的候选 issue v1 marker、task-folder 及整个 wiki repo 内同 key 的新式 wiki v1 marker；再统一判定：

- 一个一致载体族 → 沿用；wiki + issue 并存、引用不一致、同 key 多份或路径冲突 → BLOCKED。
- 零命中 → 才读取 `config.json` 选择新任务载体。无 marker 的旧 `analysis.md/.analysis.md` 是只读归档，不是可自动续写的 v1 载体；旧任务重启须请用户单独仲裁。
- 先生成稳定 `implementation_key`：issue 模式为 `issue:LOC-<主分析 issue>`；wiki 模式为 `source:<规范化需求源锚点+版本>`。在精确 wiki repo 的全部 `spec\*\implement.md` 头部查找：一份则复用其 folder，零份才创建，多份/引用冲突则 BLOCKED。此规则只适用于新建或复用的 v1 活跃实现；不回写 legacy 归档。

### issue 模式：载体选择（三分支）

| 场景 | 动作 |
|--|--|
| 会话由某个 Multica issue 触发 / 分析对象就是该需求 | 以该 issue 为**主分析 issue**；首次转换保存不可变的原始 description 快照，之后只幂等替换 marker 内分析块 |
| 从父需求切出一个新的实现单元 | 建一个主分析子 issue；创建前明确 parent/project/stage/status/assignee，stage 必须匹配父 issue barrier；不传 stage 也会进入隐式 barrier，不可随意。暂不执行用 `backlog` + 无 assignee；`todo` + agent assignee 会立即触发 |
| 同一实现单元需分散分析 | 仅为真正独立的分析边界建主 issue 的子 issue；每个子 issue 回指主 issue 和同一 `implement.md`，主 issue 在 Stage 3 前汇总子 issue 索引与最终 ⑤。冲突未解不得进入 Stage 3 |
| 本地会话、无关联 issue | 先 AskUserQuestion 询问是否已有主分析 issue 并索取 ID；只有用户明确确认不存在，才继续定标题/project/父子并创建。无法确认/无回应则 BLOCKED，禁止凭“当前上下文没看到”重复创建 |

分析子 issue 完成其边界内分析并被主 issue 汇总后，才由主分析 agent 将其置 `done`；未开始时保持 `backlog`。`done` 会参与父 issue 的显式/隐式 stage barrier 并触发系统行为，因此创建前必须纳入父流程。不得为了“放不下”而建子 issue，也不得用错误的 status/assignee/stage 组合意外调度。

### 分析模板（两模式通用 ①-⑥）

v1 analysis marker 与 `implementation_key` **两模式都必须有**。首次转换既有 issue 时，先在分析 marker 之外追加一次以下不可变快照；wiki 模式不写该快照：

```markdown
## 原始需求（首次转换快照）
<!-- spec-driven-original:v1:start -->
<首次转换前的 description 原文，逐字保留>
<!-- spec-driven-original:v1:end -->
```

两模式共用的分析块：

```markdown
<!-- spec-driven-analysis:v1:start key=<issue:LOC-n | source:规范化需求源锚点+版本> -->
> 分析日期: YYYY-MM-DD ｜ 状态: Stage 2 决策锁定 ｜ 需求最新性已确认（CP-需求最新性）
> Implementation key: issue:LOC-<主issue号>（wiki 模式为 source:<规范化需求源锚点+版本>）
> ONES 单号: <人提供的单号；多个按提供顺序用「、」分隔；未提供写「未提供」>
> YYYY-MM-DD 修订: <一句话>（仅有修订时逐行追加）

## ① 需求源锚定
- 需求源: <PRD/附件/设计文档绝对路径 或 issue 线索>（版本 / 锚定日期）
- 含图源处理: 已抽图 N 张并逐张 Read / 无图源
- 分析线索: <LOC-xx 评论 thread / 会话>
- ONES 详情: <已调用的 ones-mcp 逻辑能力、返回版本/更新时间与关键事实落点；未提供单号时写「未调用（未提供单号）」>

## ② 字段/范围清单
| 类别 | 项目 | 状态 |
|--|--|--|
（业务待确认 vs 内部工程项；解决后标注结论指向或删除线）

## ③ 证据查证表
| 字段/事实 | 代码落点 | 验证方法 | 证据 |
|--|--|--|--|

## ④ 外部源依赖追溯
| 来源 | 字段 | 单位/规范 |
|--|--|--|
（无外部依赖时保留本节，写一行「无｜—｜查证依据：<已查来源>」）

## ⑤ 决策清单
| 决策 | 选项 | 选择 | 理由 |
|--|--|--|--|
（材料级决策先 AskUserQuestion 锁定再落表；"推荐"不落此表）

## ⑥ 待联调 / 待确认
1. …（解决后用删除线标记并注明结论出处）

## 关联
- 实现计划: `D:\wiki\<wiki-folder>\spec\<task-folder>\implement.md`（Stage 3 后回填）
- wiki 模式分析文档: `D:\wiki\<wiki-folder>\spec\<task-folder>\analysis.md`
- issue 模式主分析 issue: [LOC-xx](mention://issue/<uuid>)
- issue 模式分析子 issue: [LOC-yy](mention://issue/<uuid>)（主 issue 列全量；子 issue 回指主 issue）
- 需求源附件: <路径>
<!-- spec-driven-analysis:v1:end -->
```

按当前模式只保留适用的关联行。默认六块都保留，无适用项写「无 + 查证依据」。③⑤ 是**永不省略**的结构化小节（CP-分析实质）；①②④⑥只有在写入前走 CP-分析简化审批并得到用户明确批准，才可按批准范围省略。

### issue 模式：CLI 操作规约

- 描述读写一律使用当前工作目录内 UTF-8 临时文件 + `--description-file`；不用内联 `--description` 或 stdin。成功/失败都删除临时文件。最终评论另用 `issue comment add --content-file`。
- **幂等 merge**：首次 update 把原 description 放入 `spec-driven-original:v1` marker（逐字不改）并追加 analysis marker；后续只替换 `spec-driven-analysis:v1` marker 内内容，原始 marker 与所有 marker 外未知内容保持不变。marker 缺半、重复、版本未知时 BLOCKED，不猜测修复。
- **单 writer + 尽力竞态检测**：每个分析 issue 的 description 只由主分析 agent 串行写，子 agent 返回材料，不直接 update。首次 get 保存 `description/updated_at`，构建后立即再次 get；变化则丢弃候选并重合并/BLOCKED。update 后再 get 验证。CLI 无 compare-and-swap，最后一次 get → update 仍有不可消除的竞态窗；发现/预期有人并行编辑时必须协调停写或 BLOCKED，不能声称该流程原子安全。
- 每次实质性分析更新在 marker 内 quote 头追加修订行。最终结果评论只写交付摘要/指针；不把完整分析、计划或过程日志复制进评论。

### issue 模式：降级

新任务配置为 `issue` 但 CLI/workspace 不可用 → AskUserQuestion 征求，用户明确同意后才为**本任务**降级 wiki，并在 `analysis.md` 头部记录原因与原配置。已有 issue 载体的任务不可因暂时故障另建 wiki 载体；应 BLOCKED 等待恢复。路径/资源不可写也不得通过在任意本地目录落盘来“降级”。

## 分析载体必须有实质（证据表 + 决策清单，不是需求复述）

观察到的失败：agent 把分析载体写成"需求复述"（甚至标题写成"需求文档"），把真正的证据/决策塞进 `implement.md`，于是分析载体空壳、`implement.md` 既背设计又背计划。

**分析载体是"分析设计"不是"需求拷贝"。通篇复述需求 = Stage 2 没做。** 证据与决策只在分析载体落地，`implement.md` 引用其结论：

| 内容 | 落地处 | implement.md 怎么写 |
|--|--|--|
| 字段/接口的代码落点（file:line / SHA） | 分析载体 ③证据查证表 | "落点见分析载体 ③" 一句带过 |
| code-graph 影响面 | 分析载体 ③（影响面结论作为证据行） | task 只写"该改动 impact=HIGH，见分析载体 ③"+ 对应护栏 |
| 材料级决策（数据源 / topic / 范围 / 分期 scope） | 分析载体 ⑤决策清单（先 `AskUserQuestion` 锁定） | "采用方案见 ⑤决策#N"，不重述理由 |
| ONES 返回的需求事实与查证依据 | 分析载体 ①-⑥ 的对应位置 | 顶部只写同一 ONES 单号，task 引用已锁定结论，不复制原始详情 |

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
| 接口契约：确切的方法/字段/topic/enum 名与签名、分析载体钉死的取值（数据源 / 状态集 / 单位符号 / 字段范围） | 能从契约直接推出的 import / 依赖注入 / 样板 |
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

**更新动作（D4）**：按变化类型处理，不做旧式强制双写：

| 变化 | 回写 |
|--|--|
| 仅 task / 顺序 / 实现契约偏离 | 只 Edit `implement.md` 对应正文 |
| 仅分析事实 / 决策变化 | 只同步分析载体对应行并追加修订行 |
| 两类都变 | 两者都更新 |
| ONES 单号后补 / 更正 / 撤销 | **追溯字段例外**：完成适用的详情读取后同步分析载体与 `implement.md` 顶部，清理/重验旧单号事实并追加修订行；不因追溯字段本身改已冻结的 `implementation_key` |
| 纯过程输出且未改变二者 | 不复制进任一载体 |

**执行记录（预留）**：每份新建或复用的 v1 `implement.md` 文末创建空的 `## 执行记录` 节。本次只声明它未来用于终态，不定义 writer、行格式或 commit/test/deploy 的分阶段 upsert，也不自动写任何行；这些由后续 commitID/Jenkins 方案一次性定稿。过程日志不复制进文档。Multica 强制最终评论仍照常发布简洁摘要/指针，不能把本段误读为“禁止交付评论”。

## 任务目录与文件命名

```
D:\wiki\<wiki-folder>\spec\<task-folder>\
    analysis.md      ← 仅新式 wiki 模式生成，含 v1 carrier marker + implementation_key + 可选 ONES 单号；issue 模式不生成
    implement.md     ← HOW + bite-sized tasks；顶部含全局查重用 implementation_key 与同一 ONES 单号，Stage 3 create-or-reuse；文末创建空的「## 执行记录」预留节
    （需求源附件 / 设计文档 / 基线文档等输入材料按需并存）
```

新任务的分析落点由配置决定，已有任务按持久化引用续写——见「分析载体与配置」章。**实现唯一源头**：创建前先检查，一个实现单元有且仅有一份 `implement.md`；issue 不承载第二份详细计划/日志，但保留平台强制的简洁最终评论。

- **`<wiki-folder>`**：复用现有 wiki 别名规则。源仓库 basename 通常一致（如 `D:\code\fms-server` → `D:\wiki\fms-server`），可被别名（如 `D:\code\fabusurfer` → `D:\wiki\fms-fabusurfer`）。`ls D:\wiki\` 可查。
- **`implementation_key` / `<task-folder>`**：先由主 issue LOC-n（issue 模式）或规范化需求源锚点+版本（wiki 模式）得到 key，再在整个 wiki repo 的 `spec\*\implement.md` 检索；命中一份就沿用其 folder，不能靠改名新建第二份。ONES 单号是独立追溯字段，不自动替换 key，也不因后补/更正单号另建实现目录。零命中时才从 PRD 标题/关键词命名 folder；用户已命名则沿用，拿不准先 AskUserQuestion。issue 模式主 issue 列全部子 issue 并回指 implement；每个子 issue 回指主 issue 和同一路径。
- **历史遗留**：无 v1 marker 的存量 `analysis.md/.analysis.md` 一律原地只读归档——不迁移、不改名、不回写，也不自动当成续写载体；旧任务重启需用户单独仲裁，不能同时套用“续写”和“不迁移”。新 wiki 任务的 `analysis.md` 必须带 v1 marker。
- **wiki 存储前置**：只在用户确认且当前 agent 已获写权限的**精确 wiki repo root**下创建 `spec\<task-folder>\`。路径未作为 Multica resource/checkout 提供、repo root 不明确或不可写时 BLOCKED；不得自动在宽泛 `D:\wiki` 根执行 `git init`，如确需初始化必须另行确认精确根目录。
- **git 跟踪**：`spec\` 是 wiki-folder 下的兄弟目录（与 `<module>/` 平级），不被 `document-systems` 写入的 `.gitignore` 模式（当前只忽略 `<DOC_REL>/.review.md`）匹配；`implement.md` 默认随 wiki 仓正常 commit / diff。
