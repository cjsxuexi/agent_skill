# spec-driven-implementation 重构计划：analysis.md → Multica issue 描述

> **给评估者**：本文件是供评估的计划（LOC-178），非执行清单。设计决策集中在 §2，均标注「确认状态」；用户 review 期间可直接在本文件增改内容（rev 机制同 wiki-search 计划）。
> **给执行者（评估通过后）**：按 §4 Task 逐条实现，用运行内 task tracker 记录进度，默认不改本评审计划的 checkbox（避免制造未纳入提交的脏文件）；推荐 `superpowers:executing-plans`。改动对象是 skill 文档 + `config.json`，无生产代码；"测试" = §5 的一致性 sweep、skill 校验、CLI 实测与前向场景验证。
> **rev.2 变更（2026-07-23，依用户 LOC-178 评论）**：① 纠正定位——LOC-176 不作范本，本质是「wiki 文件**平移**到 issue 描述」：①-⑥ 结构保真迁移（D2 已定）；② 载体动因补记：issue 可绑子 issue、存执行结果，后续用户将绑定 git commitID 并结合 Jenkins 跟踪投产（§1.7；Stage 5 增执行结果回流约定）；③ implement.md 引用简化为 `LOC-<n> <标题>`——实测 CLI 可直接解析 LOC-n，uuid/读取命令不再拼入（D8 已定）；④ CP-分析文档跳过 → **CP-分析简化**：分析 issue 必然存在，门禁对象从"跳过生成"变为"简化内容需用户批准"（D5 语义已定）。
> **rev.3 变更（2026-07-23，依用户 LOC-178 评论第二轮）**：① 确认 D1=C、D3=B、D7=不迁移；② 新增 **D9 实现唯一源头**（§1.8）：分析可多 issue / 子 issue，实现只有一处——`implement.md` 是唯一实现载体，issue 不承载第二份详细实现内容/日志（Multica 强制最终通知评论例外由 rev.5 补齐）；③ D4 改为 Stage 5 由 AI 自主判断同步范围；④ D5 CP 定名 **CP-分析简化审批**；⑤ D6 增加 `analysis_carrier` 双模配置。
> **rev.4 变更（2026-07-23，依用户 LOC-178 评论第三轮）**：① 「## 执行记录」只面向终态，中间过程日志不复制进 skill 管理载体；rev.5 进一步明确本次**只预留空节**，writer/格式/里程碑更新后续设计；② D6 配置改放 skill 目录 `config.json`；③ O1 确认、O2 收口、skill 不人为设置描述长度上限（Task 1 只验样本 round-trip，不代表平台无限制）。
> **rev.5 变更（2026-07-23，LOC-180 逻辑审查）**：修复配置文件未纳入实现/提交、分析多 issue 无收敛根、跨会话载体漂移、issue 描述重复包裹/并发覆盖、六块结构与④省略规则冲突、D4 与生命周期强制双写冲突、Multica 强制结果评论冲突，以及 workspace 导入无来源/绑定分支不完整等可执行性问题；补充 legacy 只读归档边界、跨 task-folder 的 `implementation_key` 查重、单 writer 与 CLI 无 CAS 残余竞态声明、路径授权、配置完整错误矩阵、子 issue 生命周期、UTF-8 skill 校验、双模式前向验证、安装态 `config.json` canary，以及 `created|updated` 导入/绑定失败回滚。

**Goal（一句话）**：重构 `/spec-driven-implementation`：新增**分析载体配置**（默认 `wiki` = 现行 `analysis.md` 零变化；开启 `issue` 后 Stage 2 分析落 **Multica issue 描述**、wiki 中本 skill 的分析/实现产物只新增 `implement.md`，需求源附件等输入仍可并存），并固化「**实现唯一源头 = implement.md**」纪律。

**Architecture（3 句）**：分析实质（①-⑥ 六块）与两个分析类 checkpoint **载体无关**；`analysis_carrier` 仅为**新任务**选择初始载体，已有任务按其持久化引用续写，避免跨会话因配置变化产生双重权威。issue 模式以一个**主分析 issue**为收敛根，可挂多个有边界的分析子 issue；主 issue 汇总子 issue 索引与最终 ⑤决策清单，`implement.md` 引用主 issue 和全部相关子 issue。实现侧仍只有一份 `implement.md`；本次只预留「## 执行记录」节，不定义自动写入，过程日志不复制到 skill 管理的文档/issue 载体；Multica 运行仍按平台契约发布一条简洁最终结果评论，权威实现内容保持在 `implement.md`。

**Tech Stack**：Markdown（SKILL.md prose）+ JSON（`config.json`）；`multica` CLI（issue get / create / update `--description-file`、skill import/get、agent skills）；PowerShell / Write 工具（UTF-8 临时文件，CP-0 约束）；git（D:\jk_file\skills 仓）；`skill-creator` 校验；多 skill 无耦合（§1.4 已查证）。

**影响文件**：
- Modify: `D:\jk_file\skills\spec-driven-implementation\SKILL.md`（现约 154 行，主要规则改动）
- Create: `D:\jk_file\skills\spec-driven-implementation\config.json`（随 skill 导入的支持文件；默认 `{"analysis_carrier":"wiki"}`）
- 不改: `wiki-search` / `export-session` / `document-systems` / `README.md`（§1.4 查证无耦合）

---

## 1. 背景与既有事实（自足，全部已实读查证）

### 1.1 现状：analysis.md 在 skill 中的角色

当前 SKILL.md（2026-07-23 实读，约 154 行）规定：

- **Stage 2 产出** `D:\wiki\<wiki-folder>\spec\<task-folder>\analysis.md`，含 6 块：① 需求源锚定 ② 字段/范围清单（业务待确认 vs 内部工程项）③ 证据查证表（字段→落点 file:line/SHA→验证方法→证据）④ 外部源依赖追溯 ⑤ 决策清单（决策→选项→选择→理由）⑥ 待联调/待确认（`SKILL.md:34`）。
- **Stage 3** `implement.md` 顶部必须以绝对路径引用 analysis.md，只引用结论不复述证据（`SKILL.md:35`）。
- **Stage 4** 派发 prompt 必须同时带两个文件的绝对路径；code agent 不得重决已钉死的决策（`SKILL.md:36`）。
- **Stage 5** 实现中发现与分析结论不符的事实必须回写 analysis.md 对应行（`SKILL.md:37`）。
- **CP-分析文档跳过**（`SKILL.md:52`）：默认必须生成；agent 想跳过 → AskUserQuestion 列 ≥2 理由请用户批准。
- **CP-分析文档实质**（`SKILL.md:53`）：必须有真实 ③⑤，通篇复述需求 = 失败；材料级决策先锁再落 ⑤。
- 其余触点：Common Rationalizations 3 行（`SKILL.md:68-70`）、Red Flags 5 条（`SKILL.md:85-89`）、「analysis.md 必须有实质」整节（`SKILL.md:91-109`）、「implement.md 生命周期」同步动作（`SKILL.md:140`）、「任务目录与文件命名」整节（`SKILL.md:144-154`）。

### 1.2 LOC-176（issue 承载分析级长文的既有实例；rev.2 起不作范本）

LOC-176（`5dddfff1-bf62-4d3a-9c4d-bcf48f06e4d5`，agent 创建的子 issue，parent=LOC-91，stage 2）的 description 是 issue 承载分析级内容的既有实例：

- `## 背景（发起依据）`——现状事实全部带代码证据（`VehicleBridgeGrpcService.pushEgoInfo` 按 `ChassisDetail.hasSany()` 归集、配置前缀 `bridge.sany-chassis`、proto 字段 `dgHowo = 31`），并引用取证 issue（LOC-174 代码核查）；
- `## 目标`（编号清单）、`## 约束与前置`（回归红线 / 门禁 / 开关规范）、`## 建议产出与验收`、`## 关联`（父 issue、基线文档 wiki 绝对路径、相关 issue）。
- 特征：证据密度达标但叙事化，无 ①-⑥ 圈号、无独立证据表。**rev.2 定位**：仅作「issue 能承载长分析文」的可行性证据；目标结构以原 analysis.md ①-⑥ **保真平移**为准（D2），不模仿其叙事形态。

### 1.3 现产 analysis.md 实例（对照）

`D:\wiki\NP_FMS\fms-server\spec\dg-ecs-rest-interface\analysis.md`（该 skill 最近一次真实产出，Stage 5 状态）：头部 quote 块（分析日期/需求源/分析线索/状态/`> 2026-07-13 修订:` 行）+ 完整 ①-⑥；③ 有 18 行证据、⑤ 有 10 项决策、⑥ 用删除线标记已解决项。说明两点：(a) 分析产物是**跨会话活文档**（修订行 + 行内改写）；(b) 决策线索本来就发生在 Multica issue thread（LOC-59/LOC-87 评论）——issue 化是把载体挪回讨论发生地。

### 1.4 跨 skill 耦合查证（本次已 grep + 实读，结论：零耦合）

| 关联方 | 事实 | 结论 |
|--|--|--|
| `wiki-search` | 宽检索显式排除 `\spec\` 目录（SKILL.md:115、search-strategy.md:148-152，把 `.analysis.md`/`spec\` 列为噪声排除项） | analysis.md 移出 wiki 不影响检索；implement.md 本来就不被检索 |
| `export-session` | 其 `analysis.md` 是自身 session 分析产物（同名不同物） | 无耦合 |
| `document-systems` | `.gitignore` 只忽略 `.review.md`；MIGRATION.md 中 analysis 字样是 `business-report-lineage-analysis.md` | 无耦合 |
| `skills/README.md` | spec-driven 行只述用途不述产物文件名（README.md:18） | 不需改 |
| 存量文件 | 7 个归档任务目录（old_project/PSA_FMS，`.analysis.md` 或 `analysis.md` + `implement.md`）+ 1 个近期目录 `NP_FMS\fms-server\spec\dg-ecs-rest-interface\`（仅 analysis.md，Stage 5 态） | 全部归档保留，见 D7 |

### 1.5 multica CLI 既有事实（`--help` 实测 + 运行时手册）

- `issue update <id> --description-file <path>`：UTF-8 文件整体替换 description；**路径必须在当前工作目录内**（`--allow-external-file` 可豁免，默认拒绝，防串档 MUL-4252）。`--description` 内联会解码转义、Windows stdin 管道会 ASCII 化非 ASCII 字符——两者都不可用于 agent 长文（与评论 `--content-file` 同源规约）。
- `issue create` 同样支持 `--description-file` / `--parent` / `--project` / `--stage` / `--status`；**agent assignee + `--status todo` 会立即触发该 agent 运行**。新分析子 issue 必须在创建前明确 parent/project/stage/status/assignee；暂不执行时用 `backlog` + 无 assignee，但 stage 仍须与父 issue 的显式/隐式 barrier 设计一致。
- `issue get <id> --output json` 的 `description` 字段即完整 markdown 原文（LOC-176/LOC-178 实测多 KB、含表格/引用块/mention 链接均完好）。
- 描述长度：用户已定**不设长度限制**（rev.4）；Task 1 仅验证 ≥10KB CJK+表格内容的 round-trip 保真（对标 dg-ecs analysis.md ≈ 8.5KB），不找上限。
- `issue get` 同时接受 uuid 与人读标识：`multica issue get LOC-176 --output json` 实测成功（2026-07-23）——`implement.md` 引用行只写 `LOC-<n>` 即可被机器解析，无需拼 uuid / 读取命令。
- `multica skill import` 不接受裸本地目录，必须二选一：`--url <受支持 URL>` 或 `--file <本地 .skill/.zip>`；导入结果以结构化 `status=created|updated|conflict|skipped|failed` 为准。`overwrite` 仅在同名 skill 已存在且当前用户是原创建者时可更新；更新保留原 skill ID 与绑定，新建后绑定是独立动作。
- 2026-07-23 实查当前 workspace：尚无 `spec-driven-implementation`，当前 agent 也无该 skill 绑定；因此首次部署预期是 `created`，不能写成必然 `overwrite/update`。本地 skills 仓领先 `origin/master` 3 个提交，未 push 前不能用 GitHub URL 代表本地新内容，Task 8 采用本地 zip 导入。

### 1.6 范围解读（评审请确认，见 O1）

Issue 原文「只在 wiki体系 存储 implement.md」解读为：**在本 skill 的产物中**只有 implement.md 留在 wiki。需求源附件、设计文档、基线文档（如 `2026-07-07-dg-shangang-ecs-adaptation-design.md`、`2026-07-15-dg-optional-feature-baseline.md`）不是本 skill 产物，仍留 `spec\<task-folder>\`，不在本次范围。

### 1.7 载体动因（rev.2 补记，rev.3 修正口径）

选 issue 做分析载体不只是"换个地方存文件"：issue 是**分析侧聚合枢纽**——分析可发散为多个子 issue、评论承载决策线索，后续由用户在 issue 侧绑定 git commitID 并与 Jenkins 结合跟踪改造是否投产（用户侧扩展，§7）。平台现成挂点：子 issue 契约（todo 立即触发 / backlog 待命 / stage 分期）与推荐 metadata 键（`pr_url` / `pipeline_status` / `deploy_url`）。这些 metadata 只可在后续方案中作为非权威状态/指针，不能替代 `implement.md`。~~rev.2 曾约定"执行结果以评论回流 issue"~~——rev.3 依用户澄清作废的是把详细执行记录回流 issue；Multica 强制的一条最终结果评论仍须保留（§1.8）。

### 1.8 实现唯一源头（rev.3 补记，用户 2026-07-23 评论点题）

用户点题：implement.md 留在 wiki 的原因是**锁定唯一实现源头**——「分析可以有多个子 issue，但是具体实现只能有一处」。落成纪律（D9）：

- 分析**发散**：一个需求可有一个主分析 issue + 多个边界明确的分析子 issue；主 issue 是索引与决策收敛根，Stage 3 前必须汇总全部相关子 issue 和无冲突的最终 ⑤决策；
- 实现**收敛**：每个实现单元先确定稳定 `implementation_key`（issue 模式=`issue:LOC-<主分析 issue>`；wiki 模式=`source:<规范化需求源锚点+版本>`），在整个 wiki repo 的 `spec\*\implement.md` 头部检索该 key；命中一份就复用其 task-folder，零命中才创建，多命中/路径冲突则 BLOCKED。所有分析 issue 回指同一路径；
- 实现计划 / task 清单 / 详细执行记录**不复制进 issue 描述或评论作为权威内容**。但 Multica-assigned run 必须按平台契约发布恰好一条简洁最终结果评论（结果状态、PR/commit、测试摘要、`implement.md` 指针）；该评论是通知/索引，不是第二实现源头；
- 本次只在 `implement.md` 文末**预留空的**「## 执行记录」节并限定未来只收终态；writer、行格式、commit/test/deploy 分阶段更新规则留待后续设计，本次不自动写行、不要求尚未知的投产状态；
- 中间尝试输出/过程测试日志不手工复制到 skill 管理的文档或 issue 载体；平台/CI 自身日志不在此禁令内。过程中发现的分析级新事实同步进分析载体，造成 plan 偏离则更新 `implement.md` 正文。

### 1.9 执行环境与持久化前提（rev.5 补记）

- 本 skill 无论哪种分析模式都要持久化 `implement.md`；执行前必须确认目标 wiki 仓**精确根目录**及 task-folder 对当前 agent 可读写、可提交。Multica 中应由已授权的 `local_directory` / `github_repo` 项目资源或 task checkout 提供；资源缺失时先向用户说明并 BLOCKED，不擅自新增持久资源。
- 当前 LOC-180 project 无 attached resources，本 run 对 `D:\jk_file\skills` / `D:\wiki` 只有读权限，不能直接执行 Task 2-7 或真实双模式写入冒烟。后续执行须在有写权限的本地环境进行，或由用户显式绑定精确资源后重新运行。
- 禁止在宽泛的 `D:\wiki` 根自动 `git init`。只在用户确认的**精确 wiki repo root**初始化；已有父/子 git work tree、路径歧义或权限不足时 BLOCKED。

---

## 2. 设计决策（评审重点；标注推荐与确认状态）

| #   | 决策                                        | 选项                                                                                                                                                                                                                                                                                                                                              | 推荐                                                                                                                   | 确认状态                                                     |
| --- | ----------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| D1 | 分析落到哪个 issue（issue 模式载体选择） | A. 一律更新触发 issue 描述 / B. 一律新建子 issue（LOC-176 模式）/ C. 三分支规则：任务=既有 issue 本身→update 并作为主分析 issue；从父需求切出新实现单元→create 主分析子 issue；同一实现单元需并行分析→在主分析 issue 下建有边界的分析子 issue；本地会话无关联 issue→AskUserQuestion 定标题/父子/项目后 create | **C**。任何新子 issue 创建前都锁定 parent/project/stage/status/assignee；暂不执行时用 `backlog` + 无 assignee，stage 按父 issue barrier 设计选择（无 stage 也是隐式 barrier，不可随意）。`todo` 会立即运行。Stage 3 前主 issue 汇总子 issue，之后才将已完成的分析子 issue置 `done`；无回应则 BLOCKED | **已定**（用户 2026-07-23：C；rev.5 补齐生命周期） |
| D2 | 描述结构 | **①-⑥ 结构保真平移**：quote 头 + ①-⑥ 全部保留；无适用内容也保留对应节并写「无（查证依据：…）」；③⑤永不省略，其余节仅经事前审批可省略。issue 模式用版本 marker 分隔首次原始需求快照与 agent 管理分析块；更新只替换分析块并保留 marker 外内容。每个分析 issue 同时只允许主分析 agent 这一名 writer，子 agent 返回材料而不直接改 description | CLI 无 compare-and-swap；双 get 只能缩小、不能消除最后一次 get 到 update 的竞态窗口。若存在并发编辑可能性就 BLOCKED/协调单 writer，不宣称原子安全 | **已定**（用户方向不变；rev.5 补幂等边界与已知竞态） |
| D3 | Stage 4 派发上下文（issue 模式） | B 扩展为：主分析 issue + 全部相关子 issue 的标识/读取命令，另将**主 issue 已汇总、无冲突的 ⑤决策清单全文**内联进派发 prompt | **B**（⑤ 是"不得重决"的判据；子 issue 决策未汇总或互相冲突 → Stage 3/4 BLOCKED。取不到 issue 且内联决策不足以消歧 → BLOCKED，不自行回退） | **已定**（用户 2026-07-23：B；rev.5 补多 issue 收敛） |
| D4 | Stage 5 回写、修订痕迹与执行结果 | **按变化类型自主判断**：分析事实/决策变 → 仅同步分析载体；plan 的 task/顺序/契约变 → 仅同步 `implement.md` 正文；两类都变 → 两者；纯过程输出且不改变两者 → 不手工持久化。`## 执行记录` 本次只预留空节，不自动写行。Multica issue run 仍发布平台强制的一条简洁最终结果评论，但不复制详细计划/过程日志 | 如左；删除生命周期章中“任何 plan 偏离都强制回写分析载体”的旧双写规则 | **已定**（方向=用户 2026-07-23 二轮；rev.5 消除强制双写与平台结果评论冲突） |
| D5 | 术语与 CP 更名/语义 | 中性术语**「分析载体」**（= wiki `analysis.md` 或主/子分析 issue 树；新任务由配置选择，旧任务按锚定续写）。CP-分析文档跳过 → **CP-分析简化审批**：默认六块，③⑤永不省略；想省/瘦身①②④⑥须在写入前列 ≥2 理由并让用户明确批准范围。CP-分析文档实质 → **CP-分析实质** | 如左；名称强调“简化”对象与“审批”动作，避免读成 CP 主动要求简化 | **已定**（语义=用户 2026-07-23；rev.5 统一省略矩阵/时机） |
| D6 | 载体配置、续写与降级 | `<skill根>\config.json` 仅接受 string `"wiki"|"issue"`；只有文件/键缺失默认 wiki，其余错误 fail closed。续写时先**收集完**所有证据再决策：implement 头引用、已知候选 issue 的 v1 marker、新式 wiki v1 marker；一个一致载体族→续写，双载体/冲突→BLOCKED，零命中→才读 config。无 marker 的存量 `analysis.md/.analysis.md` 是 D7 只读归档，不自动续写；重启旧任务仍按用户既定决定留待单独仲裁 | 本地/无关联会话在创建主 issue 前必须询问是否已有主 issue ID，并让用户明确确认“没有”；无法全局发现未知 issue，故不能自动保证查重。issue 故障仅经明确同意降级新任务，已有 issue 任务不得另建 wiki 载体 | **已定**（rev.5 补跨会话锚定、完整收集、legacy 边界与发现限制） |
| D7 | 存量迁移 | 不迁移：7+1 个既有 `analysis.md` / `.analysis.md` 原地归档（先例：skill 内 `.analysis.md` 历史遗留条款）。`dg-ecs-rest-interface` 的 Stage 5 态 analysis.md 同样归档；该任务若重启，届时再抬升为分析 issue | 如左 | **已定**（用户 2026-07-23：不用迁移） |
| D8 | 双向引用 | issue 模式：`implement.md` 顶部写 `> 主分析 issue：LOC-<n> <标题>`，有子 issue 时另写 `> 分析子 issue：LOC-a …；LOC-b …`；只放人读标识/标题，**不拼 uuid / 读取命令**。主 issue「关联」列全量子 issue，每个子 issue 回指主 issue 与同一 `implement.md`。读取方法在配置章教一次、Stage 4 prompt 带一次。wiki 模式沿用绝对路径互引；本次不新增 metadata key | 如左 | **已定**（rev.2 依实测收口 uuid 疑问；rev.5 扩展为主/子索引） |
| D9 | 实现唯一源头（§1.8） | `implementation_key` 写入 implement 头部并在整个 wiki repo 的 `spec\*\implement.md` 中查重；一份→复用其 folder，零份→创建，多份/同 key 不同路径→BLOCKED。issue 模式 key 取主 LOC-n，wiki 模式取规范化需求源锚点+版本。多个分析 issue 在 Stage 3 前收敛到一个主 issue、一个最终⑤与同一路径。简洁最终评论保留；执行记录仅预留 | 如左；解决“换 task-folder 名即可生成第二实现源头” | **已定**（用户点题；rev.5 补跨目录 identity/create-or-reuse） |

**既有小瑕疵（顺手修正，不扩范围）**：现 `SKILL.md:100` 把「code-graph 影响面」的落地处写成「analysis.md ④」，但 ④ 定义是外部源依赖追溯（§1.3 实例中影响面证据实际落在证据表）——重写该表时将影响面行的落地处改为「③证据查证表」（见 Task 5 Step 1）。

---

## 3. 全局约束

- 分析 6 块默认全部存在；无适用内容写「无 + 查证依据」，不静默删节。③证据查证表与⑤决策清单是永不省略的最小实质；①②④⑥仅能在 CP-分析简化审批**事前**明确批准的范围内省略。"复述需求=失败"、材料级决策先锁再落不变。
- **纪律载体无关**：六块实质、CP-分析简化审批、CP-分析实质在两种载体模式下同样适用；配置只选新任务载体，续写先检测已锚定载体；Stage 行与 CP 行统一用中性词「分析载体」。
- **实现唯一源头**：不得把详细实现计划/task/过程日志复制进 issue；`implement.md` 保持权威。本次只预留空的「## 执行记录」节；Multica 强制的一条最终结果评论是通知例外，不得因此省略。
- SKILL.md 既有中英混排、表格驱动的行文风格保持；不重排未触及章节。
- issue 描述长文用 `--description-file`，issue 最终评论用 `issue comment add --content-file`；两者都先在当前工作目录写 UTF-8 临时文件，并在成功/失败路径都删除（CP-0 / MUL-4252）。
- 执行前验证 `D:\jk_file\skills` 与目标 wiki repo 精确路径已被授权且可写；Multica project resource 缺失时只报告/请求绑定，不擅自修改 durable resources。
- Task 2-7 之间 SKILL.md 处于混合术语的中间态，**不逐 task 提交**；Task 7 sweep 通过后一次性 commit（对文档型改动，原子性优于高频提交——对 writing-plans 默认的显式偏离）。

---

## 4. Tasks

### Task 0: 执行前提与目标锁定

**Files:** 无改动；只做只读 preflight。

- [ ] **Step 1**: 确认执行环境对 `D:\jk_file\skills\spec-driven-implementation\` 有写权限，且目标 wiki 的**精确 repo root**可读写/提交。Multica 中先查 project resources；若资源未绑定或 sandbox 只读，向用户请求精确资源/改由本地环境执行并 BLOCKED，不尝试绕过权限。
- [ ] **Step 2**: `git -C D:\jk_file\skills status --short --branch`，记录并保留所有无关改动。当前已知 `.claude/`、`ones-mcp/` 为未跟踪路径，不能据此宣称仓库 clean，也不得 add/删除它们。
- [ ] **Step 3**: 锁定 Task 1 的测试 workspace/project、Task 8 的部署 workspace，以及新建 skill 时要绑定的目标 agent IDs；三者未明确时先 AskUserQuestion，无回应则 BLOCKED。
- [ ] **Step 4**: 读取部署 workspace 的 skill list 与目标 agent bindings，记录同名 skill 是否存在、`created_by` 是否允许 overwrite。该结果决定 Task 8 走 `created` 或 `updated` 分支，不能预设。

### Task 1: CLI 机制实测（长描述 round-trip）

**Files:** 无仓库改动；实测结论只进入本次运行的最终结果评论，不回写本评审计划。

**Interfaces:** Produces——「≥10KB CJK+表格描述可完整 round-trip」的实证结论，供 Task 2 模板收口（长度已定**不设限制**，rev.4——本测试只验保真，不找上限）。

- [ ] **Step 1**: 在当前工作目录创建 run-unique UTF-8 `./scratch-desc-<run-id>.md`：内容 ≥10KB，须含中文、markdown 表格（≥15 行证据表样例）、头部 quote 块、删除线、`[LOC-176](mention://issue/5dddfff1-bf62-4d3a-9c4d-bcf48f06e4d5)` 链接。另预先确定唯一的 `$env:TEMP` 副本路径。
- [ ] **Step 2**: 在 Task 0 锁定的测试 project 创建 `--status backlog`、无 assignee、无 stage 的 scratch issue，标题带 run-id；保存返回 id。创建属于 live side effect，若无测试 project 授权则 BLOCKED。
- [ ] **Step 3**: `multica issue get <id> --output json`，PowerShell 比对 run-unique 源文件与 JSON `description`（允许约定的尾部换行差异）。预期：表格/引用块/中文零丢失。
- [ ] **Step 4**: 改写同一 run-unique 文件（头部追加修订行），以 `--description-file` update 后再 get 比对。预期：整体替换、修订行完好。
- [ ] **Step 5**: 负路径验证：把文件复制到唯一 `$env:TEMP` 路径后执行 update。预期：被拒（工作目录外）；若平台行为不同则停止并修订规约，不能把 10KB 成功外推成“平台无限制”。
- [ ] **Step 6**: 用 `try/finally` 等价流程保证每个退出路径都执行：已创建则将 scratch issue 置 `cancelled`；删除工作目录与 `$env:TEMP` 两份临时文件。最终评论只记 pass/fail、scratch issue 标识和已清理状态，不把测试正文贴入 issue。

### Task 2: 新增配置文件与「分析载体与配置」章节

**Files:** Create `D:\jk_file\skills\spec-driven-implementation\config.json`；Modify `SKILL.md` — 插入位置：现「## analysis.md 必须有实质…」章（当前约 `SKILL.md:91`）之前。

**Interfaces:** Produces——支持文件 `config.json`；节名「分析载体与配置」；术语「分析载体」「wiki 模式」「issue 模式」「主分析 issue」「分析子 issue」；配置解析/续写优先级；版本化描述 marker；模板（首次原始需求快照 + ①-⑥ + 关联）。Task 3-6 全部引用这些名字。

- [ ] **Step 1**: 新建 `config.json`，内容严格为 `{"analysis_carrier":"wiki"}`（UTF-8、JSON object）。用 PowerShell `ConvertFrom-Json` 校验可解析、键为 string 且只取 `wiki|issue`；同时在 SKILL.md 规定：文件/键缺失才默认 wiki，不可读/非法 JSON/非 string/未知值全部 fail closed。
- [ ] **Step 2**: 插入以下完整章节文本（D1-C / D2 幂等保真 / D4 分类同步 / D5 事前简化审批 / D6 新任务配置 + 续写锚定 / D9 单实现源头）：

````markdown
## 分析载体与配置（analysis.md 的落点由配置决定）

Stage 2 先解析**该任务已锚定的载体**，只有新任务才读取配置选初始载体。分析实质（①-⑥ 六块）与分析类 checkpoint 在两种模式下完全一致。实现侧不受配置影响：一个 `<task-folder>` 有且仅有一份 `implement.md`；详细实现计划/task/过程日志不复制进 issue，Multica 的一条最终结果评论仅作通知与索引。「## 执行记录」本次只预留空节，未来写入契约另行设计。

### 存储与权限前置

先确认目标 wiki 的**精确 repo root**与 task-folder 对当前 agent 可读写、可提交；`implement.md` 在两种模式下都依赖该持久化位置。Multica runtime 未注入对应 `local_directory` / `github_repo` 资源或 task checkout 时，向用户说明并 BLOCKED；不得擅自新增 project resource，也不得在宽泛的 `D:\wiki` 根执行 `git init`。

### 配置

本 skill 目录下 `config.json`（随 skill 仓版本管理；运行时经 skill 自身 base directory 解析，不依赖 wiki 根）：

```json
{ "analysis_carrier": "wiki" }
```

- 只接受 string `"wiki"|"issue"`。文件不存在或 object 中缺键才默认 `wiki`；文件不可读、JSON 非法、根不是 object、值非 string、未知值一律报配置错误并 AskUserQuestion/BLOCKED，绝不静默回落。
- `"wiki"` → 新任务按现行路径生成 `analysis.md`，但在文件中写 v1 carrier marker + `implementation_key` 以区别 D7 legacy 归档；`"issue"` → 新任务把六块分析写入主分析 issue description，wiki 侧仍只新增 `implement.md`。
- **续写优先于配置，但禁止短路检测**：先收集 implement 头引用、当前/用户给出的候选 issue marker、task-folder 及 repo 内同 key 的新式 wiki marker，再统一判定。一个一致载体族才续写；wiki+issue 并存、引用不一致或同 key 多份 → BLOCKED。无 marker 的旧 `analysis.md/.analysis.md` 仅归档，不是可续写 v1 载体。
- 新任务在 Stage 2 首次写载体前读取一次配置并固定本任务选择；开关以仓库 `config.json` 为准，workspace 重导入会覆盖运行侧手改。

### issue 模式：载体选择（三分支）

| 场景 | 动作 |
|--|--|
| 会话由某个 Multica issue 触发 / 分析对象就是该需求 | 以该 issue 为**主分析 issue**；首次转换保存不可变的原始 description 快照，之后只幂等替换 marker 内分析块 |
| 从父需求切出一个新的实现单元 | 建一个主分析子 issue；创建前明确 parent/project/stage/status/assignee。暂不执行用 `backlog` + 无 assignee；stage 必须匹配父 issue barrier（不传 stage 也会进入隐式 barrier）。委派时 `todo` 会立即触发 |
| 同一实现单元需分散分析 | 仅为真正独立的分析边界建主 issue 的子 issue；每个子 issue 回指主 issue和同一 `implement.md`，主 issue 在 Stage 3 前汇总子 issue 索引与最终 ⑤决策。冲突未解不得进入 Stage 3 |
| 本地会话、无关联 issue | 先 AskUserQuestion 询问是否已有主分析 issue 并索取 ID；只有用户明确确认不存在，才继续定标题/project/父子并创建。无法确认/无回应则 BLOCKED，禁止凭“当前上下文没看到”重复创建 |

分析子 issue 完成其边界内分析并被主 issue 汇总后，才由主分析 agent 将其置 `done`；未开始时保持 `backlog`。`done` 会参与父 issue 的显式/隐式 stage barrier 并触发相应系统行为，因此创建前必须纳入父流程。不得为了“放不下”而建子 issue，也不得让错误的 status/assignee/stage 组合意外调度。

### 分析模板（两模式通用 ①-⑥；marker / 原始快照 / 关联为 issue 模式附加）

```markdown
## 原始需求（首次转换快照）
<!-- spec-driven-original:v1:start -->
<首次转换前的 description 原文，逐字保留；仅 update 既有 issue 分支存在>
<!-- spec-driven-original:v1:end -->

<!-- spec-driven-analysis:v1:start key=<issue:LOC-n | source:规范化需求源锚点+版本> -->
> 分析日期: YYYY-MM-DD ｜ 状态: Stage 2 决策锁定 ｜ 需求最新性已确认（CP-需求最新性）
> Implementation key: issue:LOC-<主issue号>（wiki 模式为 source:<规范化需求源锚点+版本>）
> YYYY-MM-DD 修订: <一句话>（仅有修订时逐行追加）

## ① 需求源锚定
- 需求源: <PRD/附件/设计文档绝对路径 或 issue 线索>（版本 / 锚定日期）
- 含图源处理: 已抽图 N 张并逐张 Read / 无图源
- 分析线索: <LOC-xx 评论 thread / 会话>

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
- 主分析 issue: [LOC-xx](mention://issue/<uuid>)
- 分析子 issue: [LOC-yy](mention://issue/<uuid>)（主 issue 列全量；子 issue 回指主 issue）
- 需求源附件: <路径>
<!-- spec-driven-analysis:v1:end -->
```

默认六块都保留，无适用项写「无 + 查证依据」。③⑤ 是**永不省略**的结构化小节（CP-分析实质）；①②④⑥只有在写入前走 CP-分析简化审批并得到用户明确批准，才可按批准范围省略。

### issue 模式：CLI 操作规约

- 描述读写一律使用当前工作目录内 UTF-8 临时文件 + `--description-file`；不用内联 `--description` 或 stdin。成功/失败都删除临时文件。最终评论另用 `issue comment add --content-file`。
- **幂等 merge**：首次 update 把原 description 放入 `spec-driven-original:v1` marker（逐字不改）并追加分析 marker；后续只替换 `spec-driven-analysis:v1` marker 内内容，原始 marker 与所有 marker 外未知内容保持不变。marker 缺半、重复、版本未知时 BLOCKED，不猜测修复。
- **单 writer + 尽力竞态检测**：每个分析 issue 的 description 只由主分析 agent 串行写，子 agent 返回材料，不直接 update。首次 get 保存 `description/updated_at`，构建后立即再次 get；变化则丢弃候选并重合并/BLOCKED。update 后再 get 验证。CLI 无 compare-and-swap，最后一次 get→update 仍有不可消除的竞态窗；发现/预期有人并行编辑时必须协调停写或 BLOCKED，不能声称该流程原子安全。
- 每次实质性分析更新在 marker 内 quote 头追加修订行。最终结果评论只写交付摘要/指针；不把完整分析、计划或过程日志复制进评论。

### issue 模式：降级

新任务配置为 `issue` 但 CLI/workspace 不可用 → AskUserQuestion 征求，用户明确同意后才为**本任务**降级 wiki，并在 `analysis.md` 头部记录原因与原配置。已有 issue 载体的任务不可因暂时故障另建 wiki 载体；应 BLOCKED 等待恢复。路径/资源不可写也不得通过在任意本地目录落盘来“降级”。
````

- [ ] **Step 3**: 通读插入后的章节，确认配置解析、续写优先级、marker merge、主/子收敛、生命周期和最终评论例外与前后章节无重复/冲突。

### Task 3: SOP 表 Stage 2/3/4/5 行改写

**Files:** Modify `SKILL.md:34-37`（The 6-Stage SOP 表）。

**Interfaces:** Consumes——Task 2 的节名与术语。Produces——Stage 行的新表述，Task 4-5 的 CP/红旗与其一致。

- [ ] **Step 1**: Stage 2 行 Produce 列整体替换为：

> **分析载体**（先续写已锚定载体，新任务才按配置选择；见「分析载体与配置」章）: 默认六块齐全——①需求源锚定 ②字段/范围清单 ③证据查证表 ④外部源依赖追溯 ⑤决策清单 ⑥待联调/待确认；无适用内容写「无+查证依据」。issue 模式另有版本 marker、首次原始需求快照与关联；多 issue 时主 issue 必须汇总子 issue 索引及最终 ⑤。

Stop point 列中旧跳过判断改为：**在开始产出/省略任何分析小节之前**判断是否请求简化；想简化必须先走 CP-分析简化审批，用户批准前按全量六块执行。

- [ ] **Step 2**: Stage 3 先从分析载体得到稳定 `implementation_key`，在精确 wiki repo 的全部 `spec\*\implement.md` 头部查重：一份则复用其 task-folder，零份才创建，多份/冲突则 BLOCKED。新/旧 implement 顶部均包含 `> Implementation key: ...`。wiki 模式另引 analysis.md 绝对路径；issue 模式写主分析 issue及全量子 issue 人读标识，不拼 uuid/命令。主 issue⑤未收敛不得生成计划。
- [ ] **Step 3**: Stage 4 Context 分模式：wiki 模式沿用现行 `implement.md` + `analysis.md` 两个绝对路径，不要求不存在的主 issue/内联⑤；issue 模式必须含 implement 路径、主 issue + 全量子 issue 标识及逐个读取命令、**主 issue 汇总后的⑤全文**。任一必要 issue 取不到且内联不足，或子/主⑤冲突 → BLOCKED。
- [ ] **Step 4**: Stage 5 改成 D4 决策表：分析事实/决策变→同步分析载体并加修订行；task/顺序/实现契约偏离→同步 `implement.md` 正文；两者都变→两者；纯过程输出且未改变二者→不复制进载体。保留空「## 执行记录」节但本次不自动填行。Multica issue run 仍按 runtime 用 `--content-file` 发布一条简洁最终结果评论（outcome、PR/commit、测试摘要、implement.md 指针）。

### Task 4: 两个 checkpoint 改写（CP-分析简化审批 / CP-分析实质）

**Files:** Modify `SKILL.md:52-53`（9 Non-Skippable Checkpoints 表）。

- [ ] **Step 1**: `CP-分析文档跳过` 行整体替换为（**语义变更**：跳过门禁 → 简化审批门禁，语义=用户 2026-07-23 已定、名称=受托定义）：

> | **CP-分析简化审批** | Stage 2 开始写分析载体前；或写作中首次准备省略/瘦身小节之前 | **Default = ①-⑥ 六块齐全**，无适用内容写「无 + 查证依据」。若 agent 判断可简化（单文件/纯重命名/注释或配置微调，且不碰数据流/外部依赖/跨模块/含图源），必须在省略前用 `AskUserQuestion` 列 ≥2 个具体理由，并让用户明确批准可省略的①②④⑥范围；③证据查证表与⑤决策清单不可省略。未获明确答复则按全量版，无法继续则 BLOCKED | 防止先简化后补审批；issue 只剩原始需求 / analysis.md 空壳均属变相跳过；简化决定不能由 agent 单方面作出 |

- [ ] **Step 2**: `CP-分析文档实质` 行整体替换为（③⑤ 圈号随 D2 保真迁移保留，换中性载体术语与 CP 名）：

> | **CP-分析实质** | Stage 2 正在写分析载体；多 issue 汇总完成前；或 Stage 3 正要把证据/决策写进 `implement.md` | 每个分析单元都须有真实 ③证据查证表与⑤决策清单；主分析 issue 还必须列全量子 issue 并汇总无冲突的最终 ⑤。**通篇复述需求 = 失败**。材料级决策必须先 AskUserQuestion 锁定再落⑤，不准以“推荐”躺在 `implement.md`。③⑤ 永不因简化审批而消失 | 防空壳、分散决策未收敛、plan 替用户拍板及多 issue scope 打架 |

### Task 5: 实质章 / Rationalizations / Red Flags / 生命周期 同步改写

**Files:** Modify `SKILL.md:68-71`（Rationalizations 4 行中的 3 行）、`SKILL.md:85-89`（Red Flags 5 条）、`SKILL.md:91-109`（实质章整节）、`SKILL.md:140`（生命周期更新动作）。

- [ ] **Step 1**: 「## analysis.md 必须有实质…」整节改写：标题 → `## 分析载体必须有实质（证据表 + 决策清单，不是需求复述）`；正文术语 analysis.md → 分析载体；三行落地表改为：

> | 内容 | 落地处 | implement.md 怎么写 |
> |--|--|--|
> | 字段/接口的代码落点（file:line / SHA） | 分析载体 ③证据查证表 | "落点见分析载体 ③" 一句带过 |
> | code-graph 影响面 | 分析载体 ③（影响面结论作为证据行；修正原 ④ 误标） | task 只写"该改动 impact=HIGH，见分析载体 ③"+ 对应护栏 |
> | 材料级决策（数据源 / topic / 范围 / 分期 scope） | 分析载体 ⑤决策清单（先 `AskUserQuestion` 锁定） | "采用方案见 ⑤决策#N"，不重述理由 |

③⑤ 行示例、引导语与末段原样保留（圈号结构随 D2 保真迁移不变），仅 `analysis.md` 字样 → 分析载体。

- [ ] **Step 2**: Rationalizations 逐行替换：`SKILL.md:68` 改为「默认全量；想省略①②④⑥须事前走 CP-分析简化审批，③⑤永不省略」；`:69` 换成中性术语与 CP 新名；`:70` 改为 D4 分类规则——plan-only 偏离只更新 `implement.md`，只有分析事实/决策也变才同步分析载体，禁止恢复旧式强制双写。
- [ ] **Step 3**: 新增/改写以下 Rationalizations：

> | "issue 描述太长，证据表就省了吧" | ③⑤ 永不省略；平台拒绝 payload 时 BLOCKED/报告实际错误，不能用未授权瘦身掩盖。Task 1 的 10KB 通过只证明该样本保真，不证明无平台上限 |
> | "配置是 issue 模式但没有 issue，先写个本地文件回头再挪" | 新任务走三分支；已有 issue 载体等待 CLI 恢复。只有用户明确同意才降级，禁止静默制造第二载体 |
> | "有几个分析子 issue，implement.md 引主 issue 就够了" | 主 issue 必须列全量子 issue并汇总最终⑤；implement.md 与 Stage 4 都带主/子索引。未收敛或冲突即 BLOCKED |
> | "把详细实现步骤/日志贴进 issue，final comment 也一起禁掉" | `implement.md` 是权威，但 Multica final comment 是强制通知：只发 outcome、PR/commit、测试摘要和 implement.md 指针，不复制全文 |
> | "config 写成 issues 也按默认 wiki 吧" | 只有文件/键缺失才默认；不可读、非法 JSON、类型错误、未知值全部 fail closed，避免拼写错误切错载体 |

- [ ] **Step 4**: Red Flags 逐条替换为中性载体术语与 CP 新名；`:86` 不再写“同步两文档”，改成 D4 分类判断。新增以下红旗：

> - issue update 前 marker 缺半/重复/版本未知，或二次 get 的 `description/updated_at` 已变 → 停止覆盖，重新合并或 BLOCKED
> - 新任务同时发现 `analysis.md` 与 issue marker，或准备因配置变化切换旧任务载体 → 停，请用户确定权威载体
> - 多个分析 issue 尚未由主 issue 汇总最终⑤，或准备只把一个 LOC-n 交给实现者 → 停，先收敛
> - task-folder 已有 `implement.md` 却准备再建一份，或 wiki 精确 repo root 不可写 → 停，复用/请求资源，禁止宽根 `git init`
> - 准备把详细 task/过程日志写进 issue → 停；但也不得省略 Multica runtime 强制的一条简洁最终结果评论
> - 准备往空的「## 执行记录」自动追加行 → 停：本次只预留，writer/格式/里程碑更新由后续方案定义

- [ ] **Step 5**: 「implement.md 生命周期」更新动作改成 D4 决策表，不再强制把每个 plan 偏离写进分析载体；只有偏离暴露了新的分析事实/决策时才同步相应载体。章末新增「执行记录」预留段：

> **执行记录（预留）**：`implement.md` 文末创建空的 `## 执行记录` 节。本次重构只声明它未来用于终态，不定义 writer、行格式或 commit/test/deploy 的分阶段 upsert，也不自动写任何行；这些由后续 commitID/Jenkins 方案一次性定稿。过程日志不复制进文档。Multica 强制最终评论仍照常发布简洁摘要/指针，不能把本段误读为“禁止交付评论”。

### Task 6: 「任务目录与文件命名」章改写

**Files:** Modify `SKILL.md:142-155`（整节）。

- [ ] **Step 1**: 目录树与条目替换为：

````markdown
## 任务目录与文件命名

```
D:\wiki\<wiki-folder>\spec\<task-folder>\
    analysis.md      ← 仅新式 wiki 模式生成，含 v1 carrier marker + implementation_key；issue 模式不生成
    implement.md     ← HOW + bite-sized tasks；顶部含全局查重用 implementation_key，Stage 3 create-or-reuse；文末创建空的「## 执行记录」预留节
    （需求源附件 / 设计文档 / 基线文档等输入材料按需并存）
```

新任务的分析落点由配置决定，已有任务按持久化引用续写——见「分析载体与配置」章。**实现唯一源头**：创建前先检查，一个 task-folder 有且仅有一份 `implement.md`；issue 不承载第二份详细计划/日志，但保留平台强制的简洁最终评论（D9）。

- **`<wiki-folder>`**：复用现有 wiki 别名规则。源仓库 basename 通常一致（如 `D:\code\fms-server` → `D:\wiki\fms-server`），可被别名（如 `D:\code\fabusurfer` → `D:\wiki\fms-fabusurfer`）。`ls D:\wiki\` 可查。
- **`implementation_key` / `<task-folder>`**：先由主 issue LOC-n（issue 模式）或规范化需求源锚点+版本（wiki 模式）得到 key，再在整个 wiki repo 的 `spec\*\implement.md` 检索；命中一份就沿用其 folder，不能靠改名新建第二份。零命中时才从 PRD 标题/关键词命名 folder；用户已命名则沿用，拿不准先 AskUserQuestion。issue 模式主 issue 列全部子 issue并回指 implement；每个子 issue 回指主 issue和同一路径。
- **历史遗留**：无 v1 marker 的存量 `analysis.md/.analysis.md` 一律原地只读归档——不迁移、不改名、不回写，也不被 D6 自动当成续写载体；旧任务重启需用户单独仲裁，不能同时套用“续写”和“不迁移”。新 wiki 任务的 `analysis.md` 必须带 v1 marker。
- **wiki 存储前置**：只在用户确认且当前 agent 已获写权限的**精确 wiki repo root**下创建 `spec\<task-folder>\`。路径未作为 Multica resource/checkout 提供、repo root 不明确或不可写时 BLOCKED；不得自动在宽泛 `D:\wiki` 根执行 `git init`，如确需初始化必须另行确认精确根目录。
- **git 跟踪**：`spec\` 是 wiki-folder 下的兄弟目录（与 `<module>/` 平级），不被 `document-systems` 写入的 `.gitignore` 模式（当前只忽略 `<DOC_REL>/.review.md`）匹配；`implement.md` 默认随 wiki 仓正常 commit / diff。
````

### Task 7: 全文一致性 sweep + 提交

**Files:** Modify `SKILL.md`（残余修正）与 `config.json`；临时验证副本仅放当前工作目录并清理；git commit 只含这两个目标文件。仓库当前有无关 untracked 路径，不宣称 clean。

- [ ] **Step 1**: 用 `rg`/Grep 做术语 sweep：`analysis.md` 只可出现在 wiki、历史续写或显式降级语境；CP 旧名零残留；主/子分析 issue、marker、最终评论例外、D4 分类同步、create-or-reuse 全篇一致。额外断言不存在「任何 plan 偏离都同步分析载体」「执行结果绝对不进评论」「无外部依赖时省略④」等旧语义。
- [ ] **Step 2**: 校验 `config.json`：`ConvertFrom-Json` 成功、根为 object、`analysis_carrier` 为 string `wiki`。从已安装 `skill-creator` 的 base directory 运行 `python -X utf8 scripts/quick_validate.py D:\jk_file\skills\spec-driven-implementation`；Windows 下必须 `-X utf8`，失败即修后重跑。
- [ ] **Step 3**: 在当前工作目录创建并最终删除 skill 临时副本，做配置/续写决策表验证：缺文件/缺键→新任务 wiki；`wiki`→wiki；`issue`→issue；不可读文件、非法 JSON、JSON 根非 object、值非 string、未知值→BLOCKED；已知 issue marker + config wiki→续写 issue；新式 wiki marker + config issue→续写 wiki；legacy 无 marker analysis.md→不自动续写；同时存在 wiki+issue 或引用冲突→BLOCKED。实现必须先收集全部证据再判定，不能首个命中即返回。
- [ ] **Step 4**: 用 fresh subagent/独立会话做不泄露答案的前向验证，使用 scratch/fixture、不写生产 issue/wiki，至少断言：
  - 对同一 issue fixture 连续 merge 两次后 original/analysis marker 各且仅一对，original 区字节不变，第二版 analysis 完整替换第一版，marker 外人工内容保留；二次 get 已变化时重合并或 BLOCKED。另确认单-writer 前提与 CLI 无 CAS 的残余竞态已明确，不声称可测试消除该窗口。
  - 主 issue + 两个子 issue 的⑤冲突时 Stage 3 BLOCKED；解决后主 issue **持久化**全量子索引与汇总⑤，`implement.md` 顶部列全量主/子标识，每个 issue 均回指同一 implement 路径，Stage 4 prompt 也带全量索引。
  - 默认 wiki 新任务仍生成带 v1 marker 的完整六块 `analysis.md`，Stage 3/4 沿用两个绝对路径且不创建/更新任何 issue；这是“默认零行为变化”的兼容验收。
  - repo 中已有同 `implementation_key` 的唯一 `implement.md` 时复用其 folder；同 key 跨 folder 多份或引用冲突时 BLOCKED。
  - plan-only 偏离只改 implement；分析-only 变化只改分析载体；两者变化才双写。
  - fixture 预期包含一条简洁 final comment 且无详细日志；真实安装态恰好一条评论由 Task 8 canary 验证，不在本地 fixture 假装验证平台副作用。

  若环境不支持 fresh agent，记录为阻塞，不把该验证降为可选。
- [ ] **Step 5**: 先运行 `git -C D:\jk_file\skills diff --cached --name-only`；若 index 已含两个目标路径之外的内容，保留现场并 BLOCKED，不 reset/unstage 用户内容。再执行带 `-C` 的 `diff --check`、显式 add 两个目标路径、核对 cached diff。提交用 `--only` + 精确 pathspec，避免夹带 index 中其他内容；不用 PowerShell 5.1 不支持的 `&&`：

```powershell
git -C D:\jk_file\skills add -- spec-driven-implementation/SKILL.md spec-driven-implementation/config.json
if ($LASTEXITCODE -ne 0) { throw "git add failed" }
git -C D:\jk_file\skills commit --only -m "spec-driven-implementation: 分析载体配置化与单实现源头纪律（LOC-178）" -- spec-driven-implementation/SKILL.md spec-driven-implementation/config.json
```

### Task 8: 部署到 Multica workspace + 冒烟

**Files:** 当前工作目录临时创建 `spec-driven-implementation-<run-id>.zip`（及仅在更新分支需要的回滚快照），结束后删除；workspace skill import/binding。

- [ ] **Step 1**: 在当前工作目录把 `spec-driven-implementation/SKILL.md` 与 `config.json` 打包为 root-level zip；列包确认恰含这两个文件。不得直接把裸目录传给 import，也不得用尚未 push 的 GitHub URL。若同名 skill 已存在，先用 `skill get` 保存 content/files 回滚快照并确认当前用户可 overwrite。
- [ ] **Step 2**: 执行 `multica skill import --file .\spec-driven-implementation-<run-id>.zip --on-conflict overwrite --output json`，以返回结构为准：`created|updated` 才进入验证；`failed/conflict/skipped` 立即停止并报告 reason，不能口头当成功。`updated` 不改变绑定；`created` 此时先不绑定。
- [ ] **Step 3**: `multica skill get <returned-id> --output json` 校验 name/description/content，且 `files` 中存在唯一 `config.json`、内容解析后为仓库值；缺文件/内容漂移则失败。更新分支按预存快照回滚；新建分支在尚未绑定时删除失败 skill。任何删除/回滚只针对本次返回的精确 id。
- [ ] **Step 4**: `created` 分支对 Task 0 已确认的目标 agent 逐个 additive add 并逐个验证；`updated` 分支不重复 add，但逐个与绑定快照比较。created 多 agent 绑定任一步失败：删除**本次精确 skill id**，重查所有目标 agent；若删除后集合仍与快照不同，才用预存的完整 ID 列表执行有意的 `skills set` 回滚并再次验证。updated 失败则重导入预存备份并核验绑定。不得留下部分绑定后继续。
- [ ] **Step 5**: 做一次安装态 canary，验证 daemon 真能从该 skill 的 base directory 读取 supporting `config.json`：在 Task 0 指定的测试 project 创建 run-unique scratch issue，显式要求已绑定测试 agent 调用该 skill、**只报告解析到的 config 路径/value 并在 Stage 0 前停止**；`todo` 触发后前台等待终态，检查恰好一条 agent-authored final result comment 且值为仓库值。无授权测试 project/agent 时 BLOCKED。finally 将 scratch issue `cancelled`；canary 失败按 Step 3-4 回滚 import/bindings。
- [ ] **Step 6**: 删除 zip/回滚临时文件。最终结果评论报告 commit、validator/前向测试、import status/skill id、安装态 canary、支持文件和最终 bindings；不贴完整计划或日志。

---

## 5. 验证与自检

**触点覆盖表**（§1.1 全部触点 → Task 映射；执行后逐行打勾）：

| SKILL.md 触点（现行行号） | 覆盖 Task |
|--|--|
| Stage 2 产出定义（:34） | Task 3 Step 1 |
| Stage 3 引用（:35） | Task 3 Step 2 |
| Stage 4 派发双路径（:36） | Task 3 Step 3 |
| Stage 5 回写（:37） | Task 3 Step 4 |
| CP-分析文档跳过（:52） | Task 4 Step 1 |
| CP-分析文档实质（:53） | Task 4 Step 2 |
| Rationalizations（:68-70） | Task 5 Step 2-3 |
| Red Flags（:85-89） | Task 5 Step 4 |
| 实质章（:91-109，含 :100 影响面落地瑕疵） | Task 5 Step 1 |
| implement.md 生命周期（:140）+ 执行记录预留 | Task 5 Step 5 |
| 任务目录与文件命名（:144-154） | Task 6 |
| 新章节（配置/续写/marker/主子收敛/CLI/降级） | Task 2 |
| `config.json` 支持文件与非法值 | Task 2 Step 1 + Task 7 Step 2-3 |
| 路径/资源授权与无关 worktree 变更 | Task 0 |
| skill 打包、导入、created/updated 绑定 | Task 8 |
| 存量归档 / README / 跨 skill | D7 + §1.4（零改动，已查证） |

**最终验收**：Task 0 前提全部满足；Task 1 round-trip/负路径及 cleanup 通过；术语 sweep、`config.json` 完整错误矩阵、legacy 无 marker 文件只读且不自动续写、`python -X utf8 quick_validate.py`、marker 幂等与单 writer/无 CAS 残余竞态声明、多 issue 持久收敛、同 `implementation_key` 跨 task-folder 的单 implement 复用/冲突、D4 分类与双模式 final comment 前向场景全部通过；commit 仅含 SKILL.md + config.json；workspace import 返回 `created|updated`，`skill get` 能读到正确 config，安装态 canary 能从 skill base directory 读取同值 `config.json`；created 分支绑定已添加核验或 updated 分支绑定与快照一致，任一导入/绑定/canary 失败均完成对应 created 删除或 updated 快照回滚并复核。任一项未过都不得降为“可选”后宣称完成。

---

## 6. 开放问题（评审时请用户定夺 / 补充）

- ~~**O1**~~ **已确认**（用户 2026-07-23 三轮："没问题"）：需求源附件/设计文档仍留 `spec\<task-folder>\`，本次只动分析产物。
- ~~**O2**~~ **已收口**（用户 2026-07-23 三轮）：Multica 自主运行由人在平台选「通过智能体创建 issue」触发、属平台侧交互，**不在 SKILL.md 写形态适配说明**。
- ~~**O3**~~ 已并入 D7（用户确认不用迁移；`dg-ecs-rest-interface` 归档，重启场景届时再定）。
- ~~**O4**~~ **已收口**（用户 2026-07-23 三轮）：skill **不人为设置描述长度上限**；Task 1 仅验证样本 round-trip 保真。若平台实际拒绝 payload，按真实错误 BLOCKED/报告，不静默简化。
- **O5**（用户预留）review 期间新增内容追加于此。

**已收口**：
- rev.2（2026-07-23 用户评论一）：LOC-176 不作范本，改为 ①-⑥ 结构保真平移（D2）；implement.md 引用不拼 uuid / 读取命令——实测 `multica issue get LOC-176` 直接可解析（D8）。
- rev.3（2026-07-23 用户评论二）：D1=C、D3=B、D7=不迁移；D4=Stage 5 同步范围 AI 自主判断；D5 CP 定名 **CP-分析简化审批**（受托定义）；D6=配置开关 `analysis_carrier`（默认 `wiki` 落旧式、`issue` 绑定 Multica）；D9 实现唯一源头成文（§1.8）。
- rev.4（2026-07-23 用户评论三）：「## 执行记录」面向终态、过程日志不复制进 skill 管理载体；D6 配置改放 skill 目录；O1/O2/O4 收口。
- rev.5（2026-07-23 LOC-180 逻辑审查）：不改变 D1-D9 的用户方向，补齐主分析 issue 收敛根、跨会话载体锚定与 legacy 归档边界、跨 task-folder `implementation_key` 查重、幂等 marker merge、单 writer/无 CAS 残余竞态声明、配置支持文件/完整非法值矩阵、D4 分类同步、Multica final comment 例外、路径授权、真实 zip 导入、安装态 config canary 及 created/updated 绑定验证与失败回滚；「## 执行记录」本次只预留空节。

## 7. 显式不做（本次范围外）

- 不迁移任何存量 analysis.md / .analysis.md；不改 wiki-search / export-session / document-systems / README.md（§1.4 已证零耦合）。
- 不改 implement.md 的粒度约定（「implement.md 任务粒度」章原样保留）与 writing-plans 路径覆盖机制。
- 不新增 issue metadata key、不引入新工具依赖。
- 不实现 git commitID / Jenkins 投产跟踪绑定，不定义「## 执行记录」writer/行格式/里程碑 upsert；本次只创建空节并禁止复制过程日志。平台推荐 metadata 键仅作为后续非权威状态/指针候选。Multica 强制最终结果评论不在“不做”范围内，仍必须发布一次。
- 不在本计划内执行 SKILL.md 改动（LOC-178 只交付计划）。
