---
name: wiki-search
description: Use when 任务属于以下三类场景时——① 需要理解 FMS / VMOS / 港口云控相关仓库的架构、接口、配置或业务流程；② 故障排查、线上现象定位、回答「为什么 X 不工作」；③ 实现新功能前需要理解相关模块的接口与依赖，或评估改动前需要了解已知风险。不适用场景：纯代码 review、配置文件小修改、非 wiki 体系管理的项目——不要从这类任务自动推断触发本 skill。
---

# wiki-search

在动手处理任务前先查 wiki 知识体系（架构文档与生产问题诊断树），按「任务拆解 → Wiki 检索 → 排查工具证据收集 → 问题定位 → 改进建议与风险清单」五阶段框架完成分析并输出结论。本 skill 是纯消费侧：全程只读检索，绝不修改任何 wiki 文档。

wiki 体系按「域 → 仓 → 子系统」组织，每个仓一个文档目录 `<DOC_ROOT>`，其下两类文档：

- **架构文档**：`<DOC_ROOT>\architecture.md`（仓级总览）与 `<DOC_ROOT>\<子系统>\architecture.md`（子系统文档，正文遵循 §1–§10 固定结构：§1 概述 / §2 入口 / §3 目录结构 / §4 对外接口 / §5 依赖 / §6 关键流程 / §7 数据模型 / §8 关键配置 / §9 已知问题 / §10 待确认）；
- **诊断树**：`<DOC_ROOT>\生产问题速查.md`（现象 → 根因决策树，仅部分仓已建立）。

路径占位符（`<WIKI_BASE>` / `<DOC_ROOT>` 等）的解析方法统一见 Phase 2。五阶段依序执行；非故障类任务（理解模块、实现前调研、改动评估）同样走完五阶段，只是 Phase 2 走普通路径、Phase 4 的收敛对象是任务问题的答案而非故障根源。

## 触发时机

**需要调用**（任一命中即触发）：

1. 需要理解 FMS / VMOS / 港口云控相关仓库的架构、对外接口、配置项或业务流程；
2. 故障排查、线上现象定位、回答「为什么 X 不工作」——此类任务 Phase 2 走故障定位路径；
3. 实现新功能前，需要理解相关模块的对外接口（§4）与依赖关系（§5）；
4. 评估改动前，需要了解目标模块的已知问题与风险（§9）；
5. 接手陌生模块，需要快速建立整体认知（§1 概述 / §2 入口 / §3 目录结构）。

**不需要调用**（不要从这类任务自动推断触发）：

1. 纯代码 review——diff 与代码本身已含所需上下文，不需要 wiki 背景；
2. 配置文件小修改——改动点与改法都已明确，无需架构背景；
3. 非 wiki 体系管理的项目——`<WIKI_BASE>` 下没有该仓的文档目录；
4. 通用编程 / 工具问题（语言语法、三方库用法等），与 wiki 覆盖的业务系统无关。

**判定规则（依序两问，均可操作验证）**：

1. **仓在不在 wiki 体系内？** 解析 `<WIKI_BASE>`（Phase 2 命令 ①）与 `<DOMAIN>`（命令 ②），确认 `<WIKI_BASE>\<DOMAIN>\<仓名>` 目录存在。域解析失败、且以仓名对全 wiki 宽检索（命令 ④ 第三层）零命中 → 不在体系内，不触发。
2. **任务要不要 wiki 背景？** 任务有「要解释的现象」（报错 / 告警 / 变慢 / 不工作），或需要设计意图、流程、依赖、风险知识才能安全动手 → 触发；两者皆无（照改即可的机械任务）→ 不触发。

拿不准时：用任务关键词做一次宽检索（命令 ④），有命中即触发。

## Phase 1 — 任务拆解

先理解后行动：动手前回答三问，产出 Phase 2 的检索关键词与 Phase 4 的收敛目标。

| # | 问题 | 要得到的答案 |
|---|------|-------------|
| Q1 | **What（是什么）** | 主体对象：哪个 API / 模块 / 业务流程 / 故障现象？名字是什么？属于哪个仓、哪个子系统？ |
| Q2 | **Why（为什么）** | 任务背景：生产故障 / 新功能 / 性能优化 / 技术债？——Q2 直接决定 Phase 2 走故障路径还是普通路径 |
| Q3 | **What（要实现什么）** | 功能边界：具体改什么 / 查什么？做到哪一步为止（只定位 / 给方案 / 动代码）？哪些明确不做？ |

判定「答清了没有」：每问都能用一句话填出唯一答案 = 清楚；填不出、或存在多个互斥候选 = 不清楚。**答不清哪一问，就先向用户确认哪一问**，确认清楚后才进入 Phase 2；一次只问缺的那几问，已明确的不重复问。

> **输出物**：三问的明确答案（各一句话）。Q1/Q3 提供检索关键词与收敛目标，Q2 决定 Phase 2 分支。

每问的自问模板与向用户确认的提问话术，见 [references/task-framework.md](references/task-framework.md)。

## Phase 2 — Wiki 检索

收集「应然」（设计意图）。先判场景：**有现象要解释（Q2 = 生产故障，或任务含排查 / 定位 / 报错 / 告警 / 变慢 / 为什么不工作）→ 路径 A；只有事情要做、要了解 → 路径 B。**

### 占位符解析（本文全部命令通用）

| 占位符 | 含义 | 解析方法 |
|---|---|---|
| `<WIKI_BASE>` | wiki 根目录 | 命令 ① |
| `<REPO_ROOT>` / `<仓名>` | 目标源码仓根目录 / 其最后一级目录名 | 由任务上下文给出 |
| `<DOMAIN>` | 仓所属业务域 | 命令 ②（只读解析，**不要**用 `--set`，那是维护侧操作） |
| `<DOC_ROOT>` | 该仓的文档根目录 | `<WIKI_BASE>\<DOMAIN>\<仓名>` |
| `<ENGINE_CLI>` | wiki_engine 命令行入口 | document-systems skill 安装目录下的 `scripts\wiki_engine\cli.py`（安装目录按「项目级 `.claude\skills\` → 用户级 `~\.claude\skills\`」顺序探测） |
| `<子系统>` | 仓内子系统目录名 | `<DOC_ROOT>` 下一级子目录 |
| `<检索根>` / `<关键词>` / `<N>` | 分层检索根 / 检索词 / 目标节号 | 检索根按路径 B 三层取；关键词来自 Phase 1 三问；`<N>` 按节映射表取 |

**命令 ① — 解析 `<WIKI_BASE>`**：

```powershell
(Get-Content "$env:USERPROFILE\.document-systems.json" -Encoding UTF8 | ConvertFrom-Json).wiki_base
```

**命令 ② — 解析 `<DOMAIN>`，拼出 `<DOC_ROOT>`**（取输出 JSON 的 `domain` 字段；`status` 非 `resolved` 或命令报错时**不要猜 DOMAIN**——改用更大检索根直接检索，或请用户指明目标域）：

```powershell
python -X utf8 <ENGINE_CLI> resolve-domain --repo <REPO_ROOT> --wiki <WIKI_BASE>
```

占位符解析结果示例（本行为示例值）：`wiki_base` = `D:\wiki`、仓名 = `fms-server`、解析出 `domain` = `NP_FMS` 时，`<DOC_ROOT>` = `D:\wiki\NP_FMS\fms-server`。

### 路径 A — 故障定位场景：先诊断树，再架构文档

1. **读该仓诊断树**（命令 ③）：

   ```powershell
   Get-Content "<DOC_ROOT>\生产问题速查.md" -Encoding UTF8
   ```

   按「现象根（`##` 标题）→ 判别分支 → 根因叶」走树：把用户报告的现象对照全部现象根，选最匹配的一个；沿其判别分支用手头证据（报错类型 / 日志关键字 / 监控表现）逐条排除收窄到一条；取根因叶上的候选根因与「确认 →」锚点，作为 Phase 3 的取证起点。**速查命中 ≠ 定案**，候选根因必须经 Phase 3 证据确认。
   - 现象不在树上 → 如实注明「速查暂无此现象」；
   - 文件不存在 → 注明「该仓暂无生产问题速查」。
   两种情况都继续第 2 步。
2. **架构文档补上下文**：按路径 B 分层检索；故障场景优先读 §9 已知问题、§6 关键流程。

### 路径 B — 普通任务场景：分层 grep（仓 → 域 → 全 wiki）

三层共用命令 ④ 的形状，只换 `<检索根>`；**上一层 0 命中（关键词的中英文、缩写等变体都试过）才升层**，有命中就地收窄，不要越层撒网：

| 层 | `<检索根>` |
|---|---|
| 第一层（仓级，默认起点） | `<DOC_ROOT>` |
| 第二层（域级，扩大） | `<WIKI_BASE>\<DOMAIN>` |
| 第三层（全 wiki，兜底；无法确定 DOMAIN 时也走这层） | `<WIKI_BASE>` |

**命令 ④ — 宽检索**（关键词扫 wiki 树内全部知识 md，按路径正则排除噪声）：

```powershell
Get-ChildItem "<检索根>" -Recurse -Filter *.md |
  Where-Object { $_.FullName -notmatch '\\\.|\\spec\\|\\_(?!common\\)|\\index\.md$' } |
  Select-String -Pattern "<关键词>" -Encoding UTF8
```

覆盖面：`architecture.md` 之外，还命中自定义名知识文档（如 `alarm-architecture.md`、`ops-diagnostics-runbook.md`）、`whole_architecture.md` 仓级总览、`issue\**` 排障笔记、`_common\*.md` 术语表、`生产问题速查.md`。排除项（`-notmatch` 四段依次为）：`.` 开头的文件/目录（`.review.md`、`.claude\`）、`spec\` 需求实现工作区、`_common` 以外的 `_*` 目录（`_meta\`）、`index.md` 域级导航页。

**命令 ⑤ — 节定向**（按任务类型直达目标节；`50` 为向后取行数，按节长调整）：

```powershell
Get-Content "<DOC_ROOT>\<子系统>\architecture.md" -Encoding UTF8 |
  Select-String -Pattern "^## <N>\." -Context 0,50
```

`<N>` 按任务类型从映射表取；各仓节标题措辞可能略有差异，**定位节一律按节号 `^## N\.` 匹配，勿按节名全字匹配**：

| 任务类型 | 优先 §节 | 次要 §节 |
|---------|---------|---------|
| 接口/协议理解 | §4 对外接口 | §1、§6 |
| 依赖关系 | §5 内外部依赖 | §1、§3 |
| 业务流程 | §6 关键流程 | §4、§7 |
| 数据结构/表 | §7 数据模型 | §5、§6 |
| 配置/参数 | §8 关键配置项 | §1 |
| 排查已知问题 | §9 已知问题与风险 | §6、§4 |
| 了解模块整体 | §1 概述 | §2、§3 |
| 开放性问题 | §10 待确认 | §9 |

> **输出物**：wiki 原文片段引用，格式固定——
> - 架构文档：「在 `<文件路径>` §N 中找到：<原文片段>」
> - 诊断树：「在 `<DOC_ROOT>\生产问题速查.md`「<现象根标题>」中找到：<原文片段>」
>
> **直接引用原文，不转述**。无路径、无节号的转述不可核查，禁止。

Git Bash 版命令、限子系统 / 限节的精确检索、结果太多时的收窄技巧，见 [references/search-strategy.md](references/search-strategy.md)。

## Phase 3 — 排查工具证据收集

收集「实然」（运行时实况）。wiki 提供设计意图，排查工具提供运行实况，两类信息互为补充、缺一不可。按任务类型选工具，非互斥可并用，全部只读取证：

| 任务类型 | 工具 |
|---|---|
| FMS 业务故障诊断（车辆离线 / 任务分配失败 / 任务卡住 / 告警不消 / 作业进不来 / DB·Redis 异常） | fms-diagnose |
| 查错误日志 / 报文 / 异常堆栈，接口 500 或慢 | fms-log |
| 只能经堡垒机（JumpServer Luna 终端）到达的目标机上执行命令取证（fms-log 能查到的日志不必动用） | cmdcap |
| 代码调用链追踪 / 陌生模块执行流理解 / 改动影响面评估 | gitnexus-debugging / gitnexus-exploring / gitnexus-impact-analysis |

各工具核心调用（`<SKILLS_ROOT>` = skill 安装根目录，按「项目级 `.claude\skills\` → 用户级 `~\.claude\skills\`」顺序探测取第一个存在者）：

```powershell
# fms-diagnose：先 --list 列检查项，再按现象选 check（--port 取 np / np_prod / psa / psa_prod）
python -X utf8 "<SKILLS_ROOT>\fms-diagnose\scripts\fms_diagnose.py" --list
python -X utf8 "<SKILLS_ROOT>\fms-diagnose\scripts\fms_diagnose.py" --port np --check vehicle-online

# fms-log：先 --list 确认目标，再 tail/grep（--port 取 np / np_prod / dg / psa / psa_prod / nb / nb_uat / yz；NP/NB 的 --grep 是正则，PSA/YZ 与 --loki 是子串）
python -X utf8 "<SKILLS_ROOT>\fms-log\scripts\fms_log.py" --port np --module fms-gateway --list
python -X utf8 "<SKILLS_ROOT>\fms-log\scripts\fms_log.py" --port np --module fms-gateway --grep "ERROR|Exception" --ignore-case --context 2
python -X utf8 "<SKILLS_ROOT>\fms-log\scripts\fms_log.py" --port dg --loki --list
```

```text
# cmdcap：在 Luna 终端内按序执行，每条命令独立一行；禁止用 ; 与其他命令拼行，save 不带任何参数
# 已知启动路径：fabu@fabubak02 -> ~/nb_port_prodprev/scripts/cmdcap shell；fabu@fabu02 -> ~/tools/cmdcap shell
cmdcap shell  →  <逐行执行诊断命令>  →  cmdcap save

# gitnexus 系列（目标仓未建索引或索引过期时，先在仓根目录跑 npx gitnexus analyze）
gitnexus_query({query: "<错误现象或接口路径>"}) → gitnexus_context({name: "<嫌疑函数或类>"})   # gitnexus-debugging：调用链追踪、错误来源定位
READ gitnexus://repo/<仓名>/context → 再 gitnexus_query / gitnexus_context                    # gitnexus-exploring：陌生模块结构与执行流
gitnexus_impact({target: "<符号名>", direction: "upstream"})                                  # gitnexus-impact-analysis：改动影响面，结果供 Phase 5 R4 使用
```

六个工具均为已安装 skill：**执行前优先触发对应 skill 本体**，让环境差异、凭据位置与最新注意事项进入上下文；本节只是选型与语法速查。

> **输出物**：运行时证据（诊断结论 / 日志片段 / 命令输出 / 调用链），每条标注来源（工具名 + 参数）保证可复现，如：【来源：fms-diagnose `--port np --check vehicle-online`】。

选型细则、完整参数表、港口差异与端到端场景，见 [references/diagnostic-tools.md](references/diagnostic-tools.md)。

## Phase 4 — 问题定位

综合 Phase 2（应然）与 Phase 3（实然），用 Gap 法收敛到唯一根源：

1. wiki 片段确认**应然**：设计上系统应该怎样工作；
2. 运行时证据确认**实然**：当前实际是什么状态；
3. **应然与实然的差异（Gap）= 根源**。找不到 Gap 时，说明主体对象找错（回 Phase 1）或证据不足（回 Phase 2 补检索 / 回 Phase 3 补取证）；不允许在没有 Gap 支撑时硬写结论。

**收敛判定准则**：

- ✅ **已收敛**：能写出「根源在 `<具体文件/类/配置>` 的 `<具体位置>`，原因是 `<具体事实>`」——三个空位都填了具体值，且每个断言有 Phase 2/3 的证据支撑。
- ❌ **未收敛**：「可能是 A，也可能是 B」——存在两个以上未被排除的候选，**必须继续取证排除到唯一**才能进入 Phase 5。「大概率是 X」（只有方向，无位置无证据）、「重启后恢复了」（现象消失 ≠ 根源定位）同样判未收敛。

> **输出物**：**根源陈述** = 主体对象 + 位置 + 根因事实，一句话；代码标识符（类名 / 配置键 / 表名 / 错误类）原样保留，不意译。非故障任务的收敛对象是任务问题的唯一明确答案，判定准则相同。

已收敛 / 未收敛的正反例与端到端示例，见 [references/task-framework.md](references/task-framework.md)。

## Phase 5 — 改进建议与风险清单

### 改进建议（4 行格式）

```text
现象：<用户感知到的问题/需求，用户视角表述>
根源：<Phase 4 的根源陈述，原样复用不另写>
方案：<具体改动内容，精确到文件/方法/配置项；不写「优化一下 X」类空话>
参考：[<wiki 文档 §节>](<相对 DOC_ROOT 的路径#锚点>)
```

### 风险清单（R1–R8 逐项标注）

对八个方向逐项标注「高 / 中 / 低 / 不适用」：每个方向都要过检查点，不允许跳过；「不适用」须写明理由；**高风险项必须给出缓解措施**（具体到操作层面，只写「注意风险」不算）；证据不足以判「低」时不降级，先用辅助工具补证据：

| # | 风险方向 | 检查点（一句话） | 辅助工具 |
|---|---------|----------------|---------|
| R1 | 兼容性风险 | 是否影响对外接口、已有客户端是否依赖旧行为 | wiki §4 |
| R2 | 数据风险 | 是否动表结构、要不要迁移脚本、现有数据是否仍合法 | wiki §7 + fms-diagnose |
| R3 | 性能风险 | 是否落在热点流程上、是否引入额外 DB/Redis/网络调用 | wiki §6 + fms-log |
| R4 | 依赖风险 | 共享库还是独立服务、波及哪些消费方、是否多仓联动 | wiki §5 + gitnexus-impact-analysis |
| R5 | 部署风险 | 多服务上线顺序、配置变更是否同步、能否灰度 | wiki §8 |
| R6 | 回滚风险 | 改动是否可逆、回滚步骤与窗口期 | — |
| R7 | 测试覆盖风险 | 改动路径有无现有测试、要不要补测再上线 | gitnexus-debugging |
| R8 | 已知问题叠加 | §9 是否有与本次改动交叉的条目、会不会被触发或叠加放大 | wiki §9 |

> **输出物**：4 行改进建议 + R1–R8 风险清单（高风险项带缓解措施）。

高/中/低/不适用的判定标准、空白模板与填写示例，见 [references/risk-checklist.md](references/risk-checklist.md)。

## 评估闭环

本 skill 的引导效果由外部会话评估机制检验：export-session 的 **D2 维度（会话内 wiki 使用保真度）**会审计会话中每处 wiki 引用是正确引用、凭记忆幻觉、还是误解原文。D2 报告中 wiki-search 相关触点的引用准确性，是本 skill 的迭代输入。

迭代路径：D2 发现误引导后先归因，再更新对应文件（更新对象是本 skill 自己的文件，不是 wiki 文档——wiki 内容修正走 wiki 维护侧流程，本 skill 保持只读）：

| 误引导表现 | 归因 | 更新对象 |
|---|---|---|
| 该检索到的文档没检索到 / 关键词失效 | 检索关键词或分层策略问题 | [references/search-strategy.md](references/search-strategy.md) |
| 找到了文档但引错节 | §节映射问题 | [references/search-strategy.md](references/search-strategy.md) 的节映射表 |
| 该用的排查工具没用 / 选错工具 | 工具选择矩阵问题 | [references/diagnostic-tools.md](references/diagnostic-tools.md) |
| 阶段流程走偏 / 输出物不合规 | 框架表述问题 | [references/task-framework.md](references/task-framework.md) |
| 风险漏评 / 定级失准 | 清单检查点问题 | [references/risk-checklist.md](references/risk-checklist.md) |
| 该触发没触发 / 不该触发误触发 | 触发判定问题 | 本文件「触发时机」章节与 frontmatter description |
