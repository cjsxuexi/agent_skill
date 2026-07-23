# spec-driven-implementation 重构计划：analysis.md → Multica issue 描述

> **给评估者**：本文件是供评估的计划（LOC-178），非执行清单。设计决策集中在 §2，均标注「确认状态」；用户 review 期间可直接在本文件增改内容（rev 机制同 wiki-search 计划）。
> **给执行者（评估通过后）**：按 §4 Task 逐条实现，步骤用 `- [ ]` 勾选；推荐 `superpowers:executing-plans`。改动对象是 skill 文档（prose），无生产代码；"测试" = §5 的一致性 sweep + CLI 实测。
> **rev.2 变更（2026-07-23，依用户 LOC-178 评论）**：① 纠正定位——LOC-176 不作范本，本质是「wiki 文件**平移**到 issue 描述」：①-⑥ 结构保真迁移（D2 已定）；② 载体动因补记：issue 可绑子 issue、存执行结果，后续用户将绑定 git commitID 并结合 Jenkins 跟踪投产（§1.7；Stage 5 增执行结果回流约定）；③ implement.md 引用简化为 `LOC-<n> <标题>`——实测 CLI 可直接解析 LOC-n，uuid/读取命令不再拼入（D8 已定）；④ CP-分析文档跳过 → **CP-分析简化**：分析 issue 必然存在，门禁对象从"跳过生成"变为"简化内容需用户批准"（D5 语义已定）。
> **rev.3 变更（2026-07-23，依用户 LOC-178 评论第二轮）**：① 确认 D1=C、D3=B、D7=不迁移；② 新增 **D9 实现唯一源头**（§1.8）：分析可多 issue / 子 issue，实现只有一处——`implement.md` 是唯一实现载体，实现内容与执行结果不进 issue；执行结果落 implement.md 预留「## 执行记录」节（后续用户完善），~~rev.2 的"执行结果评论回流"~~作废；③ D4 改为 **Stage 5 由 AI 自主判断同步范围**（分析载体 / implement.md / 两者）；④ D5 CP 定名 **CP-分析简化审批**（受托定义）；⑤ D6 增加**配置开关** `analysis_carrier`：默认 `wiki`（落旧式 analysis.md，现状零变化），`issue` 才绑定 Multica issue——skill 文本重构为「纪律载体无关、载体由配置解析」的双模结构（Task 2-6 相应改写）。
> **rev.4 变更（2026-07-23，依用户 LOC-178 评论第三轮）**：① 解决「执行结果 vs 唯一 implement.md」张力：「## 执行记录」**只收终态**（最终 commit SHA / 最终测试结论 / 投产状态，一次交付一行级别）；**中间过程执行结果不持久化到任何载体**——其影响以"分析级新事实 → 分析载体、plan 偏离 → implement.md 正文"落地，过程记录本身不存（D4/D9 细化）；② D6 配置改放 **skill 目录 `config.json`**（随 skill 仓版本管理、经 skill base directory 解析，去掉 wiki 根依赖；重导入以仓库值为准，Task 8 冒烟加复核）；③ O1 确认、O2 收口（不写入 skill）、长度**不设限制**（原 O4，Task 1 仅验 round-trip 保真）。

**Goal（一句话）**：重构 `/spec-driven-implementation`：新增**分析载体配置**（默认 `wiki` = 现行 `analysis.md` 零变化；开启 `issue` 后 Stage 2 分析落 **Multica issue 描述**、wiki `spec\<task-folder>\` 只保留 `implement.md`），并固化「**实现唯一源头 = implement.md**」纪律。

**Architecture（3 句）**：分析实质（①-⑥ 六块）与两个分析类 checkpoint **载体无关**，载体由配置解析——`analysis_carrier` 默认 `wiki`（现状不变），`issue` 模式落到分析 issue 的 description（经 `multica issue update/create --description-file` 读写；分析可发散为子 issue，issue 是分析侧枢纽）。实现侧收敛：`implement.md` 是**唯一实现源头**——一个 task-folder 仅一份，实现内容与执行结果不进 issue；**终态**执行结果落 implement.md 文末预留「## 执行记录」节（为 commitID / Jenkins 预留），**中间过程执行结果不持久化**；顶部引用按模式为 `analysis.md` 绝对路径或 `LOC-<n> <标题>`（CLI 可直接解析 LOC-n）。Stage 5 回写由 AI 自主判断同步范围（分析载体 / implement.md / 两者）；存量 `analysis.md` / `.analysis.md` 归档不迁移。

**Tech Stack**：Markdown（SKILL.md prose）；`multica` CLI（issue get / create / update `--description-file`）；PowerShell / Write 工具（UTF-8 临时文件，CP-0 约束）；git（D:\jk_file\skills 仓）；多 skill 无耦合（§1.4 已查证）。

**影响文件**：
- Modify: `D:\jk_file\skills\spec-driven-implementation\SKILL.md`（唯一实现文件，155 行，全部改动集中于此）
- 不改: `wiki-search` / `export-session` / `document-systems` / `README.md`（§1.4 查证无耦合）

---

## 1. 背景与既有事实（自足，全部已实读查证）

### 1.1 现状：analysis.md 在 skill 中的角色

当前 SKILL.md（2026-07-23 版，155 行）规定：

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
- `issue create` 同样支持 `--description-file` / `--parent` / `--project` / `--stage` / `--status`；**agent assignee + `--status todo` 会立即触发该 agent 运行**（子 issue 创建契约）——分析 issue 创建时默认不带 assignee 或用 `--status backlog`。
- `issue get <id> --output json` 的 `description` 字段即完整 markdown 原文（LOC-176/LOC-178 实测多 KB、含表格/引用块/mention 链接均完好）。
- 描述长度：用户已定**不设长度限制**（rev.4）；Task 1 仅验证 ≥10KB CJK+表格内容的 round-trip 保真（对标 dg-ecs analysis.md ≈ 8.5KB），不找上限。
- `issue get` 同时接受 uuid 与人读标识：`multica issue get LOC-176 --output json` 实测成功（2026-07-23）——`implement.md` 引用行只写 `LOC-<n>` 即可被机器解析，无需拼 uuid / 读取命令。

### 1.6 范围解读（评审请确认，见 O1）

Issue 原文「只在 wiki体系 存储 implement.md」解读为：**在本 skill 的产物中**只有 implement.md 留在 wiki。需求源附件、设计文档、基线文档（如 `2026-07-07-dg-shangang-ecs-adaptation-design.md`、`2026-07-15-dg-optional-feature-baseline.md`）不是本 skill 产物，仍留 `spec\<task-folder>\`，不在本次范围。

### 1.7 载体动因（rev.2 补记，rev.3 修正口径）

选 issue 做分析载体不只是"换个地方存文件"：issue 是**分析侧聚合枢纽**——分析可发散为多个子 issue、评论承载决策线索，后续由用户在 issue 侧绑定 git commitID 并与 Jenkins 结合跟踪改造是否投产（用户侧扩展，§7）。平台现成挂点：子 issue 契约（todo 立即触发 / backlog 待命 / stage 分期）与推荐 metadata 键（`pr_url` / `pipeline_status` / `deploy_url`）。~~rev.2 曾约定"执行结果以评论回流 issue"~~——rev.3 依用户澄清作废：执行结果属于实现侧，只落 `implement.md`（§1.8）。

### 1.8 实现唯一源头（rev.3 补记，用户 2026-07-23 评论点题）

用户点题：implement.md 留在 wiki 的原因是**锁定唯一实现源头**——「分析可以有多个子 issue，但是具体实现只能有一处」。落成纪律（D9）：

- 分析**发散**：一个需求的分析可分布在主 issue + 多个分析子 issue；
- 实现**收敛**：一个 `<task-folder>` 有且仅有一份 `implement.md`，所有分析 issue 的「关联」都指向它；
- 实现计划 / task 清单 / 执行结果**不写入 issue 描述或评论**作为权威内容——issue 侧只放分析与 implement.md 路径链接；
- **终态**执行结果（最终 commit SHA / 最终测试结论 / 投产状态）落 `implement.md` 文末预留的「## 执行记录」节（一次交付一行级别；占位约定，行格式后续由用户结合 commitID / Jenkins 完善）；
- **中间过程执行结果不持久化到任何载体**（rev.4）——每轮尝试输出、过程测试日志不存档：过程中发现的分析级新事实经 Stage 5 同步进分析载体，造成 plan 偏离则更新 implement.md 正文；过程记录本身若入「执行记录」会把唯一实现源头稀释成过程日志。

---

## 2. 设计决策（评审重点；标注推荐与确认状态）

| #   | 决策                                        | 选项                                                                                                                                                                                                                                                                                                                                              | 推荐                                                                                                                   | 确认状态                                                     |
| --- | ----------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| D1 | 分析落到哪个 issue（issue 模式载体选择） | A. 一律更新触发 issue 描述 / B. 一律新建子 issue（LOC-176 模式）/ C. 三分支规则：任务=既有 issue 本身→update 该 issue；分析从父需求切出新单元→create 子 issue；本地会话无关联 issue→create 新 issue（AskUserQuestion 定标题/父子/项目） | **C**（子 issue 分支用于从父需求切出的分析单元；update 分支必须原样保留原始需求节，见 Task 2 模板） | **已定**（用户 2026-07-23：C） |
| D2 | 描述结构 | **①-⑥ 结构保真平移**：quote 头（分析日期 / 需求源 / 状态 / 修订行）+ ① 需求源锚定 ② 字段/范围清单 ③ 证据查证表 ④ 外部源依赖追溯 ⑤ 决策清单 ⑥ 待联调/待确认 全部原样（两模式共用同一结构）；issue 模式附加「关联」节（回指 implement.md）与 update 分支的「原始需求」节。不做叙事化改写；想省/瘦身任何小节 → CP-分析简化审批（D5） | 如左（~~rev.1 曾在「①-⑥ 保守迁移」与「LOC-176 叙事型」间取舍~~） | **已定**（用户 2026-07-23 评论：wiki 文件移到 issue 描述，LOC-176 不作范本） |
| D3 | Stage 4 派发上下文（issue 模式） | A. 只给 issue 标识，subagent 自己 `multica issue get` / B. 标识 + 读取命令 + **⑤决策清单全文内联进派发 prompt** | **B**（⑤ 是"不得重决"的判据，不能依赖 subagent 环境有 CLI；取不到 issue 且内联决策不足以消歧 → BLOCKED，不自行回退。wiki 模式沿用现行双路径派发，不受影响） | **已定**（用户 2026-07-23：B） |
| D4 | Stage 5 回写、修订痕迹与执行结果 | **同步范围由 AI 自主判断**：分析结论变 → 同步分析载体（issue 模式 `issue update` 描述 + 头部修订行；wiki 模式 Edit `analysis.md` + 修订行）；plan 偏离 → 同步 `implement.md`（生命周期章）；可能两者同时。**终态执行结果落 `implement.md`「## 执行记录」预留节**（最终 commit SHA / 最终测试结论 / 投产状态，一次交付一行级别；占位约定，行格式后续用户完善）；**中间过程执行结果不持久化**（分析级新事实→分析载体、plan 偏离→implement.md 正文，过程记录本身不存，rev.4）；不以评论/描述进 issue（~~rev.2 结果评论回流~~作废） | 如左 | **已定**（方向=用户 2026-07-23 二轮；终态/过程之分=三轮）；「执行记录」行格式后续完善 |
| D5 | 术语与 CP 更名/语义 | 中性术语**「分析载体」**（= wiki `analysis.md` 或**分析 issue**，由配置决定；Stage 行 / CP 行统一用它）。CP-分析文档跳过 → **CP-分析简化审批**（受托定名：与 CP-分析实质 平行；"简化"点明被门禁的行为、"审批"点明动作——先 `AskUserQuestion` 批准才能简化，消除"这个 CP 让我简化"的歧义）；语义：默认全量六块，想省/瘦身任何小节 → 列 ≥2 理由请用户批准。CP-分析文档实质 → **CP-分析实质**（不变） | 如左 | **已定**（语义=用户 2026-07-23；名称=用户委托、本计划定为 CP-分析简化审批） |
| D6 | 载体配置与降级 | **配置开关**：`<skill根>\config.json`（即 `D:\jk_file\skills\spec-driven-implementation\config.json`，skill 目录自带）键 `analysis_carrier`——`"wiki"`（**默认**；文件或键缺失同义）= 现行 analysis.md 流程，现状零变化；`"issue"` = 绑定 Multica issue（本计划新流程）。解析时机：Stage 2 开写分析载体前经 skill 自身 base directory 读一次，会话内不切换。issue 模式下 CLI 不可用 / 任务不属于任何 workspace → `AskUserQuestion` 征求，显式降级本次为 wiki 模式（analysis.md 头部标注「降级产物：multica CLI 不可用（配置 issue 模式）」）；禁止静默降级 | 如左（配置随 skill 仓版本管理，无需依赖 wiki 根解析；开关以仓库值为准——workspace 重导入会以仓库副本覆盖运行侧手改，Task 8 冒烟含开关值复核） | **已定**（用户 2026-07-23：配置开关默认落旧式；rev.4 依用户建议改放 skill 目录） |
| D7 | 存量迁移 | 不迁移：7+1 个既有 `analysis.md` / `.analysis.md` 原地归档（先例：skill 内 `.analysis.md` 历史遗留条款）。`dg-ecs-rest-interface` 的 Stage 5 态 analysis.md 同样归档；该任务若重启，届时再抬升为分析 issue | 如左 | **已定**（用户 2026-07-23：不用迁移） |
| D8 | 双向引用 | issue 模式：implement.md 顶部引用行只写 `> 分析 issue：LOC-<n> <标题>`——实测 `multica issue get LOC-176` 可直接解析人读标识（§1.5），**uuid 与读取命令不拼入引用行**；读取方法在「分析载体与配置」章教一次、Stage 4 派发 prompt 带一次（uuid 仅在 issue 描述/评论内做 mention 链接时才需要）；分析 issue「关联」节回指 implement.md 绝对路径（Stage 3 后回填）。wiki 模式：沿用现行绝对路径互引。**不新增** metadata key（后续 Jenkins 绑定的天然落点是平台推荐键 `pr_url` / `pipeline_status` / `deploy_url`，用户侧扩展） | 如左 | **已定**（rev.2 依实测收口用户疑问） |
| D9 | 实现唯一源头（§1.8） | 一个 `<task-folder>` 有且仅有一份 `implement.md`，多个分析 issue / 子 issue 收敛指向它；实现计划 / task 清单 / 执行结果不写入 issue 描述或评论作为权威内容，issue 侧只放分析与 implement.md 路径链接；终态执行结果落 implement.md「## 执行记录」预留节、中间过程执行结果不持久化（D4，rev.4）。配套红旗与 rationalization 见 Task 5 | 如左 | **已定**（用户 2026-07-23 评论点题） |

**既有小瑕疵（顺手修正，不扩范围）**：现 `SKILL.md:100` 把「code-graph 影响面」的落地处写成「analysis.md ④」，但 ④ 定义是外部源依赖追溯（§1.3 实例中影响面证据实际落在证据表）——重写该表时将影响面行的落地处改为「③证据查证表」（见 Task 5 Step 1）。

---

## 3. 全局约束

- 分析 6 块的**实质要求一字不减**（证据查证表、决策清单两个表格式、"复述需求=失败"、材料级决策先锁再落）——本次只换载体，不降纪律。
- **纪律载体无关**：六块实质、CP-分析简化审批、CP-分析实质在两种载体模式下同样适用；载体机制（配置 / 三分支 / CLI / 降级）集中在「分析载体与配置」一章，Stage 行与 CP 行统一用中性词「分析载体」。
- **实现唯一源头**：所有改写不得引入"实现内容 / 执行结果进 issue"的表述（§1.8 / D9）；终态执行结果只落 `implement.md`「## 执行记录」预留节，**中间过程执行结果不持久化**（rev.4）。
- SKILL.md 既有中英混排、表格驱动的行文风格保持；不重排未触及章节。
- 所有 agent 长文一律 `--description-file` + 工作目录内 UTF-8 临时文件（CP-0 / MUL-4252 同源规约），用后即删。
- Task 2-7 之间 SKILL.md 处于混合术语的中间态，**不逐 task 提交**；Task 7 sweep 通过后一次性 commit（对文档型改动，原子性优于高频提交——对 writing-plans 默认的显式偏离）。

---

## 4. Tasks

### Task 1: CLI 机制实测（长描述 round-trip）

**Files:** 无仓库改动；产出验证记录追加到本文件 §6 下方（或 review 评论）。

**Interfaces:** Produces——「≥10KB CJK+表格描述可完整 round-trip」的实证结论，供 Task 2 模板收口（长度已定**不设限制**，rev.4——本测试只验保真，不找上限）。

- [ ] **Step 1**: 用 Write 工具在当前工作目录写 `./scratch-desc.md`（UTF-8）：内容 ≥10KB，须含中文、markdown 表格（≥15 行证据表样例）、头部 quote 块、删除线、`[LOC-176](mention://issue/5dddfff1-bf62-4d3a-9c4d-bcf48f06e4d5)` 链接。
- [ ] **Step 2**: `multica issue create --title "scratch: 分析载体验证（验证后作废）" --description-file ./scratch-desc.md --status backlog --output json`，记下返回 id。不带 assignee（防触发运行）。
- [ ] **Step 3**: `multica issue get <id> --output json`，PowerShell 比对：`(Get-Content ./scratch-desc.md -Raw -Encoding UTF8)` 与 json `description` 字段应一致（允许尾部换行差异）。预期：表格/引用块/中文零丢失。
- [ ] **Step 4**: 改写 `./scratch-desc.md`（头部追加一行 `> 2026-XX-XX 修订: round-trip 验证`），`multica issue update <id> --description-file ./scratch-desc.md`，再 get 比对。预期：整体替换、修订行完好。
- [ ] **Step 5**: 负路径验证：把文件复制到 `$env:TEMP` 后 `multica issue update <id> --description-file <TEMP路径>`。预期：被拒（工作目录外），确认 MUL-4252 规约表述准确。
- [ ] **Step 6**: 清理：`multica issue status <id> cancelled`；`Remove-Item ./scratch-desc.md`。把 round-trip 结论记入本文件 §6。

### Task 2: 新增章节「分析载体与配置」

**Files:** Modify `D:\jk_file\skills\spec-driven-implementation\SKILL.md` — 插入位置：现「## analysis.md 必须有实质…」章（`SKILL.md:91`）之前。

**Interfaces:** Produces——节名「分析载体与配置」、术语「分析载体」「wiki 模式」「issue 模式」「分析 issue」、配置键 `analysis_carrier`、模板小节（quote 头 + 原始需求 + ①-⑥ + 关联）。Task 3-6 的行文全部引用这些名字。

- [ ] **Step 1**: 插入以下完整章节文本（D1=C / D2=保真平移 / D4=AI 自主同步 + 执行记录预留 / D5=CP-分析简化审批 / D6=配置开关 / D9=实现唯一源头 的定稿形态）：

````markdown
## 分析载体与配置（analysis.md 的落点由配置决定）

Stage 2 分析产出的**载体由配置解析**，分析实质（①-⑥ 六块）与分析类 checkpoint 在两种模式下完全一致。实现侧不受配置影响：`implement.md` 永远是**唯一实现源头**——一个 `<task-folder>` 仅一份，实现计划 / task 清单 / 执行结果不写入 issue 描述或评论（issue 侧只放分析与 implement.md 路径链接）；**终态**执行结果落 `implement.md` 文末「## 执行记录」预留节，**中间过程执行结果不持久化**（见「implement.md 生命周期」章）。

### 配置

本 skill 目录下 `config.json`（随 skill 仓版本管理；运行时经 skill 自身 base directory 解析，不依赖 wiki 根）：

```json
{ "analysis_carrier": "wiki" }
```

- `"wiki"`（**默认**；文件或键缺失同义）→ 现行流程：分析写 `D:\wiki\<wiki-folder>\spec\<task-folder>\analysis.md`，现状零变化。
- `"issue"` → 分析**原结构平移**落 **Multica issue 的 description**（下称「分析 issue」）：quote 头 + ①-⑥ 与 analysis.md 完全一致，另加「关联」节；分析可发散为多个子 issue（issue 是分析侧枢纽，后续用户在此绑定 commitID 与 Jenkins 投产跟踪）；wiki 侧该任务只存 `implement.md`（需求源附件/设计文档按需并存）。
- 解析时机：Stage 2 开写分析载体前读一次；会话内不切换模式。
- 开关以**仓库 `config.json` 值**为准：启用 = 仓库改为 `"issue"`（本地即时生效）并重导入同步 workspace 副本；运行侧手改会被下次重导入覆盖。

### issue 模式：载体选择（三分支）

| 场景 | 动作 |
|--|--|
| 会话由某个 Multica issue 触发 / 分析对象就是该 issue 的需求 | `multica issue update <id> --description-file` 更新该 issue 描述。**原始需求文字必须原样保留为 `## 原始需求` 节**——描述更新是整体替换，丢了找不回：先 `issue get` 取原文，再拼装新描述 |
| 分析从父需求/基线中切出一个新的实现单元 | `multica issue create --parent <父id> --description-file …` 建子 issue（LOC-176 模式）。**不带 assignee**（或 `--status backlog`）——agent assignee + todo 会立即触发运行 |
| 本地会话、无关联 issue | `AskUserQuestion` 定标题/项目/父子后 `multica issue create` |

### 分析模板（两模式通用 ①-⑥；「原始需求」「关联」为 issue 模式附加节）

```markdown
> 分析日期: YYYY-MM-DD ｜ 状态: Stage 2 决策锁定 ｜ 需求最新性已确认（CP-需求最新性）
> YYYY-MM-DD 修订: <一句话>（仅有修订时逐行追加）

## 原始需求
（仅"更新既有 issue"分支保留；原文原样，不得改写）

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
（无外部依赖时整节省略，并在 ① 注明"无外部源依赖"）

## ⑤ 决策清单
| 决策 | 选项 | 选择 | 理由 |
|--|--|--|--|
（材料级决策先 AskUserQuestion 锁定再落表；"推荐"不落此表）

## ⑥ 待联调 / 待确认
1. …（解决后用删除线标记并注明结论出处）

## 关联
- 实现计划: `D:\wiki\<wiki-folder>\spec\<task-folder>\implement.md`（Stage 3 后回填）
- 相关 issue: [LOC-xx](mention://issue/<uuid>)（issue 链接无副作用；member/agent mention 会触发通知/运行，描述里禁用）
- 需求源附件: <路径>
```

③⑤ 是**必备结构化小节**（CP-分析实质）。任何小节的省略/瘦身都不是 agent 单方决定——走 CP-分析简化审批（`AskUserQuestion` 请用户批准）。

### issue 模式：CLI 操作规约

- 读写一律 `--description-file`：先用文件写工具把 UTF-8 内容写到**当前工作目录内**的临时文件（如 `./analysis-desc.md`），update/create 后 `Remove-Item`。不用内联 `--description`（解码转义）、不用 stdin 管道（Windows 下非 ASCII 被 ASCII 化，CP-0 同源问题）。`--description-file` 默认拒绝工作目录外路径（防串档，MUL-4252）。
- 读取：`multica issue get <id> --output json`，`description` 字段即分析全文。
- 修订：每次实质性更新在描述头部 quote 块追加一行 `> YYYY-MM-DD 修订: <一句话>`；是否在会话结果评论中提及修订点由 AI 视沟通需要自定（D4：同步范围 AI 自主判断）。
- 执行结果**不进 issue**：终态结果（最终 commit SHA / 最终测试结论 / 投产状态）落 `implement.md` 文末「## 执行记录」预留节，中间过程结果不持久化（实现唯一源头，D9）。

### issue 模式：降级

配置为 `issue` 但 multica CLI 不可用 / 当前任务不属于任何 Multica workspace → `AskUserQuestion` 征求用户，显式降级**本次**为 wiki 模式（`analysis.md` 头部标注「降级产物：multica CLI 不可用（配置 issue 模式）」）。**禁止静默降级。**
````

- [ ] **Step 2**: 通读插入后的章节，确认与前后章节（Red Flags / 实质章）无重复表述、无断裂引用。

### Task 3: SOP 表 Stage 2/3/4/5 行改写

**Files:** Modify `SKILL.md:34-37`（The 6-Stage SOP 表）。

**Interfaces:** Consumes——Task 2 的节名与术语。Produces——Stage 行的新表述，Task 4-5 的 CP/红旗与其一致。

- [ ] **Step 1**: Stage 2 行 Produce 列整体替换为：

> **分析载体**（由配置解析，见「分析载体与配置」章：默认 wiki 模式 = 现行 `analysis.md` 路径；issue 模式 = 分析 issue 描述。两模式实质相同）: ① 需求源锚定 (PRD 路径 / 版本 / 锚定日期 / 含图源处理) ② 字段/范围清单 (业务待确认 vs 内部工程项) ③ 证据查证表 (字段 → 落点 → 验证方法 → 证据/SHA) ④ 外部源依赖追溯 (jar / proto / 单位 / 坐标系) ⑤ 决策清单 (决策 → 选项 → 选择 → 理由) ⑥ 待联调 / 待确认（issue 模式另加「关联」节与 update 分支的「原始需求」节）

Stop point 列中「also evaluate whether `analysis.md` can be skipped — if you think yes, you MUST ask the user to confirm (see CP-分析文档跳过)」改为「also evaluate whether 分析内容可以简化 — if you think yes, you MUST ask the user to confirm (see CP-分析简化审批)」。

- [ ] **Step 2**: Stage 3 行中引用改为：**Top of `implement.md` MUST cite the 分析载体**——wiki 模式沿用现行绝对路径引用；issue 模式为 `> 分析 issue：LOC-<n> <标题>`（CLI 可直接按 LOC-n 解析，**不拼 uuid / 读取命令**——读取方法见「分析载体与配置」章）。「do NOT repeat evidence already in `analysis.md`」术语改为「…already in 分析载体」。其余（writing-plans path override、altitude override）不动。
- [ ] **Step 3**: Stage 4 行派发要求替换为：**Dispatch prompt's Context section MUST include**: (i) `implement.md` 绝对路径（primary task carrier）；(ii) 分析载体引用——wiki 模式：`analysis.md` 绝对路径（现行）；issue 模式：LOC-n 标识 + 读取命令（`multica issue get LOC-<n> --output json`）+ **⑤决策清单全文内联**（防实现环境无 CLI 时自作决定）。Code agent MUST: not re-decide what is already pinned in 分析载体 ⑤；issue 模式下无法读取分析 issue 且内联决策不足以消歧 → return BLOCKED, do not self-fallback。
- [ ] **Step 4**: Stage 5 行中「**sync `analysis.md`** — …MUST be written back to the corresponding row in `analysis.md`」替换为：**sync 分析载体** — 实现中发现与分析结论不符的事实（如字段最终读自 A 非 B）MUST 回写分析载体对应行（wiki 模式 Edit `analysis.md`；issue 模式 `multica issue update --description-file`；均在头部 quote 块追加修订行）；**同步范围由 AI 自主判断**（分析载体 / `implement.md` / 两者，D4）；终态执行结果落 `implement.md`「## 执行记录」预留节（中间过程结果不持久化），**不进 issue**（D9）。行尾产出物清单「+ `analysis.md` + `implement.md` all consistent」改为「+ 分析载体 + `implement.md`（含执行记录）all consistent」。

### Task 4: 两个 checkpoint 改写（CP-分析简化审批 / CP-分析实质）

**Files:** Modify `SKILL.md:52-53`（9 Non-Skippable Checkpoints 表）。

- [ ] **Step 1**: `CP-分析文档跳过` 行整体替换为（**语义变更**：跳过门禁 → 简化审批门禁，语义=用户 2026-07-23 已定、名称=受托定义）：

> | **CP-分析简化审批** | End of Stage 2, about to enter Stage 3 | **Default = 全量分析实质落分析载体（①-⑥ 六块齐全，载体见「分析载体与配置」章）**。If you (the agent) judge 本任务可以简化（单文件改动 / 纯重命名 / 注释或配置微调——AND 不碰数据流 / 外部依赖 / 跨模块 / 含图需求源），**you MUST use `AskUserQuestion` to list ≥ 2 concrete reasons and let the user decide 简化范围**。Until the user explicitly agrees, you must produce the full version | 同现行（"agent 悄悄跳过 → Stage 0-2 纪律脱钩 → 重蹈 C-01~C-05"）+ issue 描述停留在原始需求 / analysis.md 空壳 = 变相跳过；简化决定不能由 agent 单方面做出 |

- [ ] **Step 2**: `CP-分析文档实质` 行整体替换为（③⑤ 圈号随 D2 保真迁移保留，换中性载体术语与 CP 名）：

> | **CP-分析实质** | Stage 2 正在写分析载体；或 Stage 3 正要把"证据查证表 / 影响面 / 决策(选项·选择·理由) / file:line 落点"写进 `implement.md` | 分析载体必须含真实的 ③证据查证表（字段 → 落点 file:line/SHA → 验证方法 → 证据）与 ⑤决策清单（决策 → 选项 → 选择 → 理由）；**通篇复述需求 = 失败**。材料级决策（数据源 / topic / 字段范围 / 部署 guard / 分期 scope）必须先 `AskUserQuestion` 锁定再落 ⑤，**不准以"推荐"形态躺在 `implement.md`**。证据/决策只在分析载体落地，`implement.md` 引用结论 | 分析载体空壳化 → `implement.md` 反背 Code Evidence/Impact/Design Decision（双重臃肿）；数据源等关键决策被 plan 悄悄拍板、两次生成 scope 打架 |

### Task 5: 实质章 / Rationalizations / Red Flags / 生命周期 同步改写

**Files:** Modify `SKILL.md:68-71`（Rationalizations 4 行中的 3 行）、`SKILL.md:85-89`（Red Flags 5 条）、`SKILL.md:91-109`（实质章整节）、`SKILL.md:140`（生命周期更新动作）。

- [ ] **Step 1**: 「## analysis.md 必须有实质…」整节改写：标题 → `## 分析载体必须有实质（证据表 + 决策清单，不是需求复述）`；正文术语 analysis.md → 分析载体；三行落地表改为：

> | 内容 | 落地处 | implement.md 怎么写 |
> |--|--|--|
> | 字段/接口的代码落点（file:line / SHA） | 分析载体 ③证据查证表 | "落点见分析载体 ③" 一句带过 |
> | code-graph 影响面 | 分析载体 ③（影响面结论作为证据行；修正原 ④ 误标） | task 只写"该改动 impact=HIGH，见分析载体 ③"+ 对应护栏 |
> | 材料级决策（数据源 / topic / 范围 / 分期 scope） | 分析载体 ⑤决策清单（先 `AskUserQuestion` 锁定） | "采用方案见 ⑤决策#N"，不重述理由 |

③⑤ 行示例、引导语与末段原样保留（圈号结构随 D2 保真迁移不变），仅 `analysis.md` 字样 → 分析载体。

- [ ] **Step 2**: Rationalizations 逐行替换：`SKILL.md:68`「这次很简单…不用写 `analysis.md`」→「这次很简单…分析载体不用写全六块」，Reality 改为「默认全量。想简化 → 触发 CP-分析简化审批 → `AskUserQuestion` 列 ≥2 条理由请用户批准。agent 不能单方面决定」；`SKILL.md:69` 中「`analysis.md` 我写了啊」→「分析载体我写了啊」（③⑤ 圈号引用保留原样）、「CP-分析文档实质」→「CP-分析实质」；`SKILL.md:70` 中「+ `analysis.md` 同步记录偏离原因」→「+ 分析载体同步记录偏离原因（issue 模式描述追加修订行）」。
- [ ] **Step 3**: 新增 3 行 Rationalizations：

> | "issue 描述太长，证据表就省了吧" | 简化 = CP-分析简化审批 门禁，先问用户。dg-ecs 分析 ≈8.5KB 完整六块照样可落 issue 描述（Task 1 round-trip 实测）；③⑤ 是纪律核心，长度不是砍它们的理由 |
> | "配置是 issue 模式但没有 issue，先写个本地文件回头再挪" | 走「分析载体与配置」章三分支：无关联 issue → `AskUserQuestion` 后 `issue create`；CLI 不可用才走显式降级，禁止静默落盘 |
> | "把实现步骤 / task 清单 / 执行结果写进 issue 描述评论里更方便" | 实现唯一源头是 `implement.md`（D9）：分析可发散多 issue，实现只一处；issue 侧只放分析与 implement.md 路径链接，终态执行结果落 implement.md「## 执行记录」节（中间过程不持久化） |

- [ ] **Step 4**: Red Flags 逐条替换：`SKILL.md:85`「without `analysis.md` 存在、且用户没明确授权跳过」→「without 分析载体实质存在、且用户没批准简化」+「CP-分析文档跳过」→「CP-分析简化审批」；`SKILL.md:86`「同步两文档」→「同步 implement.md 与分析载体」；`SKILL.md:88`「`analysis.md` 通篇是需求复述、没有 ③证据查证表 / ⑤决策清单」→「分析载体通篇是需求复述、没有 ③证据查证表 / ⑤决策清单」+「CP-分析文档实质」→「CP-分析实质」；`SKILL.md:89`「锁进 `analysis.md` ⑤」→「锁进分析载体 ⑤」。新增 3 条：

> - （issue 模式）准备 `issue update` 覆盖描述、但新描述里没有保留原`## 原始需求`/原始需求文字 → 描述替换是破坏性的，先 `issue get` 取回原文再拼装（见「分析载体与配置」章）
> - 准备把实现 task 清单 / 执行结果写进 issue 描述或评论 → 停：实现唯一源头是 `implement.md`（含「## 执行记录」节）；issue 只放分析与链接（D9）
> - 每轮执行完就想把过程结果 append 进「## 执行记录」→ 停：该节**只收终态**（最终 commit / 最终结论 / 投产状态）；过程日志不持久化，其影响以"分析结论变化 / plan 偏离"分别同步（D4）

- [ ] **Step 5**: 「implement.md 生命周期」两处改写：(a) `SKILL.md:140` 更新动作改为：直接 Edit `implement.md` 对应章节；**同步在分析载体的「⑥ 待联调 / 待确认」或「⑤ 决策清单」中追加一行说明偏离原因**（wiki 模式直接 Edit；issue 模式 `multica issue update --description-file` + 头部修订行）；同步范围由 AI 自主判断（D4）。(b) 章末新增「执行记录」预留段：

> **执行记录（预留）**：`implement.md` 文末保留 `## 执行记录` 节，**只收终态**——最终 commit SHA / 最终测试结论 / 投产状态，一次交付一行级别，**不是过程日志**（行格式为占位约定、后续结合 commitID / Jenkins 投产跟踪完善）。中间过程执行结果不持久化：过程中发现的分析级新事实经 Stage 5 同步分析载体，plan 偏离更新本文件正文。执行结果**不进 issue**（实现唯一源头，D9）。

### Task 6: 「任务目录与文件命名」章改写

**Files:** Modify `SKILL.md:142-155`（整节）。

- [ ] **Step 1**: 目录树与条目替换为：

````markdown
## 任务目录与文件命名

```
D:\wiki\<wiki-folder>\spec\<task-folder>\
    analysis.md      ← 仅 wiki 模式（默认配置）生成；issue 模式下分析在 issue 描述、此文件不生成
    implement.md     ← HOW + bite-sized tasks（接口契约+测试用例粒度，非完整 code body；Stage 3 产出，覆盖 writing-plans 默认路径）；文末保留「## 执行记录」预留节（仅终态）
    （需求源附件 / 设计文档 / 基线文档等输入材料按需并存）
```

分析产出的落点由配置决定——见「分析载体与配置」章。**实现唯一源头**：一个 task-folder 有且仅有一份 `implement.md`；实现计划与执行结果不进 issue（D9）。

- **`<wiki-folder>`**：复用现有 wiki 别名规则。源仓库 basename 通常一致（如 `D:\code\fms-server` → `D:\wiki\fms-server`），可被别名（如 `D:\code\fabusurfer` → `D:\wiki\fms-fabusurfer`）。`ls D:\wiki\` 可查。
- **`<task-folder>`**：默认由 code agent 用 PRD 标题 / 任务关键词梳理出小写连字符名（如 `kafka-vehicle-data-report`）；用户已经命名则沿用；agent 拿不准 → 在首次落盘（wiki 模式 `analysis.md` / issue 模式 `implement.md`）之前用 `AskUserQuestion` 让用户拍板文件夹名。issue 模式下分析 issue「关联」节与 `implement.md` 互相回指（issue 记 implement.md 绝对路径；implement.md 顶部记 issue 标识）；wiki 模式沿用现行路径互引。
- **历史遗留**：旧任务目录下的存量 `analysis.md` 及更早的带前导点 `.analysis.md` 一律原地归档——不迁移、不改名、不回写；读旧任务目录时两种文件都可能遇到。新任务：wiki 模式继续产出 `analysis.md`（不带前导点）；issue 模式分析走分析 issue。
- **wiki 根不存在时**：本 skill 直接创建 `D:\wiki\<wiki-folder>\spec\<task-folder>\` 完整路径（不依赖 `document-systems` 必须先初始化过架构 wiki）。如果 `D:\wiki\` 本身不是 git work tree，按 `document-systems` 的方式 `git init` 一次。
- **git 跟踪**：`spec\` 是 wiki-folder 下的兄弟目录（与 `<module>/` 平级），不被 `document-systems` 写入的 `.gitignore` 模式（当前只忽略 `<DOC_REL>/.review.md`）匹配；`implement.md` 默认随 wiki 仓正常 commit / diff。
````

### Task 7: 全文一致性 sweep + 提交

**Files:** Modify `SKILL.md`（残余修正）；git commit（D:\jk_file\skills 仓，当前 clean）。

- [ ] **Step 1**: `Grep pattern="analysis\.md" path=D:\jk_file\skills\spec-driven-implementation`。预期残留必须全部处于以下语境：wiki 模式正文（配置章 / Stage 行括注 / 目录章树 / 实质章术语说明）、历史遗留条款、issue 模式降级小节。**issue 模式独立表述与 CP 行主语中不得出现**；发现语境外残留即修。
- [ ] **Step 2**: `Grep pattern="分析文档|分析 issue|分析载体" -i` 复查：CP 旧名（CP-分析文档跳过/实质）零残留，新名（**CP-分析简化审批** / CP-分析实质）全篇一致；Stage 行 / CP 行统一用中性词「分析载体」，「分析 issue」仅出现在 issue 模式语境；①-⑥ 圈号是正式结构（D2 保真迁移），保留不动；frontmatter description（`SKILL.md:3`）不含 analysis.md，确认无需改。
- [ ] **Step 3**: writing-plans 式自检三问过一遍（见 §5 覆盖表）：每个 §1.1 触点行都能指到 Task 2-6 的某一步；无 "TBD/待补/适当处理" 空话（「执行记录」行格式除外——它是 D4 显式预留，不是含糊）；术语（分析载体、wiki 模式、issue 模式、分析 issue、③证据查证表、⑤决策清单、CP-分析简化审批、CP-分析实质、执行记录、唯一实现源头）全篇一致。
- [ ] **Step 4**: 提交：`git -C D:\jk_file\skills add spec-driven-implementation/SKILL.md && git -C D:\jk_file\skills commit -m "spec-driven-implementation: 分析载体配置化（wiki 默认 / Multica issue 可选）+ 实现唯一源头纪律（LOC-178）"`。

### Task 8: 部署到 Multica workspace + 冒烟

**Files:** 无本地文件；workspace skill 重导入。

- [ ] **Step 1**: 按 `/multica-skill-importing` 的工作区导入路径（`POST /api/skills/import` 对应 CLI）以 `--on-conflict overwrite` 重导入 `spec-driven-implementation`；绑定沿用现状（additive，不 replace-all）。执行时以该 skill 文档为准。
- [ ] **Step 2**: 冒烟：导入结果 JSON 确认 overwrite 成功；workspace skill 列表可见且 description 未劣化；**复核导入副本 `config.json` 的 `analysis_carrier` 值与仓库一致**（重导入以仓库值覆盖运行侧手改，D6）。可选深冒烟：下一个真实需求任务首次走新流程时，人工核对分析 issue 与 implement.md 互指完整（作为验收，不阻塞本次）。

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
| 新章节（配置/载体/模板/CLI/降级） | Task 2 |
| 存量归档 / README / 跨 skill | D7 + §1.4（零改动，已查证） |

**最终验收**：Task 7 两个 grep 全部符合预期残留清单；Task 1 round-trip 实证记录在案；commit + 重导入完成。

---

## 6. 开放问题（评审时请用户定夺 / 补充）

- ~~**O1**~~ **已确认**（用户 2026-07-23 三轮："没问题"）：需求源附件/设计文档仍留 `spec\<task-folder>\`，本次只动分析产物。
- ~~**O2**~~ **已收口**（用户 2026-07-23 三轮）：Multica 自主运行由人在平台选「通过智能体创建 issue」触发、属平台侧交互，**不在 SKILL.md 写形态适配说明**。
- ~~**O3**~~ 已并入 D7（用户确认不用迁移；`dg-ecs-rest-interface` 归档，重启场景届时再定）。
- ~~**O4**~~ **已收口**（用户 2026-07-23 三轮）：**不设长度限制**——skill 不设上限、无需超限策略；Task 1 仅验证 round-trip 保真。
- **O5**（用户预留）review 期间新增内容追加于此。

**已收口**：
- rev.2（2026-07-23 用户评论一）：LOC-176 不作范本，改为 ①-⑥ 结构保真平移（D2）；implement.md 引用不拼 uuid / 读取命令——实测 `multica issue get LOC-176` 直接可解析（D8）。
- rev.3（2026-07-23 用户评论二）：D1=C、D3=B、D7=不迁移；D4=Stage 5 同步范围 AI 自主判断；D5 CP 定名 **CP-分析简化审批**（受托定义）；D6=配置开关 `analysis_carrier`（默认 `wiki` 落旧式、`issue` 绑定 Multica）；D9 实现唯一源头成文（§1.8）。
- rev.4（2026-07-23 用户评论三）：「## 执行记录」**只收终态**、中间过程执行结果不持久化（D4/D9 细化）；D6 配置改放 **skill 目录 `config.json`**；O1 确认、O2 不写入 skill、长度不设限。**至此 D1-D9 全部已定、O1-O4 全部收口**——计划收敛，待用户批准后按 §4 执行。

## 7. 显式不做（本次范围外）

- 不迁移任何存量 analysis.md / .analysis.md；不改 wiki-search / export-session / document-systems / README.md（§1.4 已证零耦合）。
- 不改 implement.md 的粒度约定（「implement.md 任务粒度」章原样保留）与 writing-plans 路径覆盖机制。
- 不新增 issue metadata key、不引入新工具依赖。
- 不实现 git commitID / Jenkins 投产跟踪的绑定，也不定稿「## 执行记录」节的行格式（均为用户后续完善，§1.8 / D4）；本次仅在 implement.md 预留**终态**节位并立下"执行结果不进 issue、中间过程结果不持久化"的纪律，另指明平台推荐 metadata 键（`pr_url` / `pipeline_status` / `deploy_url`）为后续绑定的天然挂点。
- 不在本计划内执行 SKILL.md 改动（LOC-178 只交付计划）。
