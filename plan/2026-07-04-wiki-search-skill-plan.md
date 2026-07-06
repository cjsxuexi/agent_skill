# wiki-search Skill 实施计划（rev.2）

> **rev.2 变更（2026-07-04）**：根据用户评估反馈更新设计决策：① DA 触发方式改为「评估任务是否需要 wiki → 触发」；② DB 故障定位场景先查 prod-issue-quickref；③ 新增 Phase 3 排查工具调用层（cmdcap / fms-diagnose / fms-log / gitnexus）；④ 处理流程由四阶段扩展为五阶段。

> **给评估者**：本文件是供评估的计划，非执行清单。所有设计决策已在"用户评估确认"列注明状态。确认后进入执行。
> **给执行者（评估通过后）**：按 Task 逐条实现，步骤用 `- [ ]` 勾选；推荐 superpowers:executing-plans。

**Goal（一句话）**：创建 `/wiki-search` skill，在 agent 处理任务时评估是否需要查 wiki（`/document-systems` 架构文档体系 + `/prod-issue-quickref` 诊断决策树），按照「任务拆解→wiki 检索→排查工具证据收集→问题定位→改进建议+风险清单」五阶段框架输出结论；通过 `export-session` D2 维度评估引导准确度。

**Architecture（3 句）**：`SKILL.md`（prose）承载触发判定、检索策略与任务分析框架；故障定位场景**先查 `prod-issue-quickref` 诊断树做初步分诊，再查 `document-systems` 架构文档补充上下文**，并按需调用排查工具（`/fms-diagnose` / `/fms-log` / `/cmdcap` / `gitnexus` 系列）收集运行时证据。Skill 是**纯消费侧（只读），绝不修改任何 wiki 文档**；诊断工具也全部只读。

**Tech Stack**：Markdown（SKILL.md/references/）；PowerShell / Git Bash grep（`-Encoding UTF8`）；`wiki_engine resolve-domain` CLI（复用 document-systems 引擎）；`/fms-diagnose` / `/fms-log` / `/cmdcap` / `gitnexus-*`（外部工具，按需调用）；`export-session` D2（外部评估）；无新增三方依赖。

---

## 1. 背景与既有事实（自足）

### 1.1 Wiki 体系现状

`D:\wiki\` 包含两类 skill 维护的文档：

**类型 A — `/document-systems` 维护（架构文档）**
```
D:\wiki\
├── NP_FMS\fms-server\fms-gateway\architecture.md   # 子系统文档 §1-§10
├── NP_FMS\fms-server\fms-core\architecture.md
├── old_project\fabusurfer\architecture.md
└── ...（三个域，多个仓库，多个子系统）
```

**类型 B — `/prod-issue-quickref` 维护（诊断决策树）**
```
D:\wiki\
└── old_project\fabusurfer\生产问题速查.md           # 现象→根因诊断树
```

每个子系统文档遵循 §1-§10 标准结构（§1 概述 / §4 对外接口 / §5 依赖 / §6 关键流程 / §7 数据模型 / §8 配置 / §9 已知问题 / §10 待确认）。

### 1.2 排查工具现状（已安装）

| Skill | 作用 | 适用场景 |
|-------|------|---------|
| `/fms-diagnose` | FMS 业务系统自动诊断（MySQL/Oracle + Redis + Loki 取证） | FMS 故障：车辆离线/任务失败/调度异常等 |
| `/fms-log` | 按港口查 FMS 服务日志（PSA=Loki / NP=k8s / NB=SSH） | 需要查具体错误日志时 |
| `/cmdcap` | 通过 JumpServer Luna 终端捕获远程命令输出 | 无法直接 SSH 的目标服务器诊断 |
| `gitnexus-debugging` | 代码级 bug 追踪、调用链分析（GitNexus 图查询） | 代码调用链、接口追踪 |
| `gitnexus-exploring` | 代码结构理解、执行流浏览 | 理解陌生模块时辅助 |
| `gitnexus-impact-analysis` | 改动影响面分析 | 改动安全性评估（配合 Phase 5 风险清单） |

### 1.3 现状问题

Agent 缺乏系统性 wiki 检索指引：
- 凭记忆引用 wiki（`export-session` D2 标"低置信疑似"）
- 不用 wiki 直接分析（丢失背景，分析偏差）
- 有了排查工具但不知何时调用、与 wiki 如何配合

---

## 2. 设计决策（★ 已由用户评估确认）

| 决策 | 选项 | 状态 |
|------|------|------|
| **DA — 触发方式** | 评估任务是否需要查 wiki（document-systems 或 prod-issue-quickref）→ 触发 | ✅ 用户确认 |
| **DB — 检索范围** | 故障定位优先查 `prod-issue-quickref`（生产问题速查.md）→ 再查架构文档 | ✅ 用户确认 |
| **DC — 检索结果使用** | 直接引用原文片段（锚路径+节），不转述 | ✅ 用户确认 |
| **DD — 评估闭环** | `export-session` D2 纯 prose 声明 | ✅ 用户确认 |
| **DE — 新增排查工具** | 集成 `/cmdcap` / `/fms-diagnose` / `/fms-log` / `gitnexus-*` 作为证据收集层 | ✅ 用户要求新增 |

---

## 3. 五阶段处理框架（锁定）

### Phase 1 — 任务拆解（先理解后行动）

agent 调用本 skill 后首先回答三问，不清楚则先向用户确认：

| 问题 | 输出 | 示例 |
|------|------|------|
| **What（是什么）** | 主体对象：API / 模块 / 业务流程 / 故障现象 | `fms-gateway 鉴权`、`JobOrder 卡死` |
| **Why（为什么）** | 任务背景：生产故障 / 新功能 / 性能优化 / 技术债 | 生产问题、需求评审 |
| **What（要实现什么）** | 功能边界：具体改什么/查什么，边界在哪 | 分析根因 / 实现接口 / 评估改动 |

> **输出物**：三问明确答案，作为 Phase 2 的检索关键词和 Phase 4 的收敛目标。

### Phase 2 — Wiki 检索（信息收集，完整优先）

**触发判定（本 skill 的核心入口逻辑）**：
- 任务涉及 FMS/VMOS/港口云控相关仓库的架构、接口、配置、业务流程 → 需要查 `/document-systems` 维护的架构文档
- 任务是故障排查、现象定位、"为什么 X 不工作" → 需要查 `/prod-issue-quickref` 维护的诊断树
- 两者可并用；纯代码任务（不涉及 wiki 体系）→ 跳过本 skill

**检索顺序（关键：故障定位场景优先级不同）**：

#### 2.A 故障定位场景（先诊断树，再架构文档）

1. **首先**：定位并读取该仓的 `生产问题速查.md`（由 `/prod-issue-quickref` 维护）：
   ```powershell
   Get-Content "<DOC_ROOT>\生产问题速查.md" -Encoding UTF8
   ```
   - 按现象在树里找匹配 `##` 根 → 沿「**判别**」分支收窄 → 到「**根因**」叶子获取候选根因
   - 找到匹配：直接引用原文片段（路径 + 节），作为 Phase 3 的分诊起点
   - 未找到匹配：如实注明「速查暂无此现象」，继续往下

2. **其次**：在架构文档中补充上下文（同「普通任务场景」下的分层检索）

#### 2.B 普通任务场景（直接查架构文档）

1. **定位 DOC_ROOT**：
   ```
   WIKI_BASE = C:\Users\admin\.document-systems.json → wiki_base
   python -X utf8 <ENGINE_CLI> resolve-domain --repo <REPO_ROOT> --wiki <WIKI_BASE>
   → DOMAIN → DOC_ROOT = <WIKI_BASE>/<DOMAIN>/<REPO_NAME>
   ```

2. **分层 grep（仓→域→全 wiki）**：

   **第一层（仓级，精准）**：
   ```powershell
   Select-String -Pattern "<关键词>" -Path "<DOC_ROOT>\**\architecture.md" -Recurse -Encoding UTF8
   ```

   **第二层（域级，扩大）**：第一层无结果时：
   ```powershell
   Select-String -Pattern "<关键词>" -Path "D:\wiki\<DOMAIN>\**\architecture.md" -Recurse -Encoding UTF8
   ```

   **第三层（全 wiki，兜底）**：前两层均无结果时：
   ```powershell
   Select-String -Pattern "<关键词>" -Path "D:\wiki\**\architecture.md" -Recurse -Encoding UTF8
   ```

3. **节定向（任务类型→目标 §节映射）**：

   | 任务类型 | 优先 §节 | 次要 §节 |
   |---------|---------|---------|
   | 接口/协议理解 | §4 对外接口 | §1 概述、§6 关键流程 |
   | 依赖关系 | §5 内外部依赖 | §1 概述、§3 目录结构 |
   | 业务流程 | §6 关键流程 | §4、§7 数据模型 |
   | 数据结构/表 | §7 数据模型 | §5、§6 |
   | 配置/参数 | §8 关键配置项 | §1 |
   | 排查已知问题 | §9 已知问题与风险 | §6、§4 |
   | 了解模块整体 | §1 概述 | §2 入口、§3 目录 |
   | 开放性问题 | §10 待确认 | §9 |

   节定向 grep 示例：
   ```powershell
   # 定位 §9 节起始行，取后 50 行
   Get-Content "<DOC_ROOT>\<subsystem>\architecture.md" -Encoding UTF8 |
     Select-String -Pattern "^## 9\." -Context 0,50
   ```

**原则：先保证完整（宁可多读），再收窄精确（去掉无关噪声）。**

> **输出物**：从 wiki 中找到的相关片段，明确标注「在 [文件路径]§N 中找到：...」（直接引用原文，不转述）。

### Phase 3 — 排查工具证据收集（按任务类型按需调用）

wiki 提供「设计意图」，排查工具提供「运行时实况」。两类信息缺一不可。

**按任务类型选择工具（非互斥，可并用）**：

#### 3.1 FMS 业务故障诊断 → `/fms-diagnose`

```bash
# 先 --list 看有哪些检查项
python scripts/fms_diagnose.py --port np --list
# 按现象选对应检查
python scripts/fms_diagnose.py --port np --check vehicle-online
python scripts/fms_diagnose.py --port psa --check psa-solace-intake
```

- 从 MySQL/Oracle + Redis + Loki 自动取证
- 输出 `status` / `headline` / `evidence` / `suggestions`
- **适用**：车辆离线/任务失败/调度异常/告警/Solace 进料/DB-Redis 异常

#### 3.2 日志分析 → `/fms-log`

```bash
# NP：查模块日志文件
python scripts/fms_log.py --port np --module fms-gateway --grep "ERROR" --context 2
# PSA：Loki 查日志
python scripts/fms_log.py --port psa --app fms-jobflow --grep "No handler found" --minutes 30
```

- **适用**：查具体错误报文、接口 500/慢、异常堆栈

#### 3.3 需要在远程服务器执行命令 → `/cmdcap`

通过 JumpServer Luna 终端捕获命令输出（无法直接 SSH 时）：
```bash
# Luna 终端内运行
cmdcap shell        # 开始录制
<执行诊断命令>
cmdcap save         # 刷出本批输出到文件
```

- **适用**：需要在堡垒机后目标服务器跑 `kubectl`/`systemctl`/`top` 等命令取结果

#### 3.4 代码级追踪 → `gitnexus-*`

```
# 调用链追踪（bug 排查）
gitnexus_query({query: "<错误现象或 API 路径>"})
gitnexus_context({name: "<嫌疑函数/类>"})
READ gitnexus://repo/{name}/process/{name}

# 改动影响面（Phase 5 配合使用）
gitnexus_impact({target: "X", direction: "upstream"})
```

- `gitnexus-debugging`：追踪调用链、定位错误来源
- `gitnexus-exploring`：理解陌生模块结构、执行流
- `gitnexus-impact-analysis`：评估改动影响面（Phase 5 风险 R4 必用）

> **输出物**：运行时证据（诊断结论 / 日志片段 / 命令输出 / 调用链图），明确标注来源（工具名 + 参数）。

### Phase 4 — 问题定位（收敛到唯一根源）

综合 Phase 2（wiki 上下文：设计意图）+ Phase 3（运行时证据：实际状态），定位问题：

**收敛判定准则**：
- ✅ **已收敛**：「根源在 `<具体文件/类/配置>` 的 `<具体位置>`，原因是 `<具体事实>`」
- ❌ **未收敛**：「可能是 A，也可能是 B」——必须继续收集证据排除，直到唯一

**收敛过程**：
1. Phase 2 的 wiki 片段确认「应然」（设计意图是什么）
2. Phase 3 的运行时证据确认「实然」（当前实际是什么）
3. Gap（应然 vs 实然的差异）= 根源

> **输出物**：「根源陈述」= 主体对象 + 位置 + 根因事实（一句话，代码标识符原样保留）。

### Phase 5 — 改进建议 + 风险清单

#### 5.1 改进建议（4 行格式）

```
现象：<用户感知到的问题/需求>
根源：<Phase 4 的根源陈述>
方案：<具体改动内容，精确到文件/方法/配置>
参考：[<wiki 文档 §节>](<相对路径#锚点>)
```

#### 5.2 风险清单（8 个方向，需全面，避免遗漏）

对每个方向标注「高/中/低/不适用」：

| # | 风险方向 | 检查点 | 辅助工具 |
|---|---------|--------|---------|
| R1 | **兼容性风险** | ① 改动是否影响对外接口（§4）？② 已知客户端是否依赖此接口？③ API 版本策略？ | wiki §4 |
| R2 | **数据风险** | ① 是否影响 DB 表结构（§7）？② 是否需要迁移脚本？③ 现有数据是否仍合法？ | wiki §7 + fms-diagnose |
| R3 | **性能风险** | ① 改动是否在热点流程（§6）上？② 是否引入额外 DB/Redis/网络调用？③ 吞吐/延迟影响？ | wiki §6 + fms-log |
| R4 | **依赖风险** | ① 改动是共享库还是独立服务？② 所有消费方是否受影响（§5 下游）？③ 是否需要多仓联动？ | wiki §5 + gitnexus-impact-analysis |
| R5 | **部署风险** | ① 多服务上线顺序？② 配置变更（§8）是否同步？③ 灰度策略可行？ | wiki §8 |
| R6 | **回滚风险** | ① 改动是否可逆？② 回滚步骤？③ 回滚窗口期？ | — |
| R7 | **测试覆盖风险** | ① 改动路径有无现有测试？② 是否需要补测试再上线？③ 边界条件覆盖？ | gitnexus-debugging |
| R8 | **已知问题叠加** | ① §9（已知问题）是否有与本次改动交叉的条目？② 改动是否可能触发 §9 缺陷？ | wiki §9 |

> 高风险项必须给出缓解措施建议。

---

## 4. SKILL.md 触发判定（DA 实现细节）

SKILL.md 的 `description` 声明 skill 适用场景（供 harness 推断），同时在 `## 触发时机` 章节内给 agent 明确判定规则：

**需要调用本 skill 的场景**：
- 任务涉及 FMS / VMOS / 港口云控相关仓库（NP_FMS / PSA_FMS / old_project 域下）的架构、接口、配置、业务流程理解
- 任务是故障排查、线上现象定位、"为什么 X 不工作"
- 实现新功能前需要理解相关模块接口/依赖（§4/§5）
- 评估改动前需要了解已知风险（§9）

**不需要调用的场景**：
- 纯代码 review（不需要 wiki 背景）
- 配置文件小修改
- 非 wiki 体系管理的项目

---

## 5. File Structure

```
D:\jk_file\skills\wiki-search\          # 源码（git 仓）
├── SKILL.md                             # 主 skill（触发判定 + 五阶段框架）
└── references\
    ├── search-strategy.md               # 分层 grep 指引 + §节映射表 + grep 命令示例
    ├── task-framework.md                # Phase 1-5 详解（含输出物规格 + 端到端示例）
    ├── diagnostic-tools.md              # 排查工具调用指引（Phase 3 详细参考）【新增】
    └── risk-checklist.md                # 风险清单模板（Phase 5 用）

安装路径：C:\Users\admin\.claude\skills\wiki-search\
```

---

## 6. Tasks

> prose skill 的「测试」= 在真实 wiki + 工具场景干跑。每个任务有可核验交付物。

### Task 1：脚手架 + SKILL.md 骨架

**Files:** Create `SKILL.md`

- [ ] Step 1：建 `wiki-search\references\` 目录。
- [ ] Step 2：写 SKILL.md frontmatter（name / description，description 覆盖触发场景：FMS/VMOS/港口云控故障排查、功能实现前理解模块、改动影响评估；**注明不从非 wiki 体系任务自动推断**）。
- [ ] Step 3：写正文章节骨架：
  - `## 触发时机`（Phase DA 判定规则）
  - `## Phase 1 — 任务拆解`
  - `## Phase 2 — Wiki 检索`
  - `## Phase 3 — 排查工具证据收集`
  - `## Phase 4 — 问题定位`
  - `## Phase 5 — 改进建议与风险清单`
  - `## 评估闭环`
- [ ] 核验：frontmatter 合法，章节完整，触发场景清晰。

### Task 2：检索策略（search-strategy.md）

**Files:** Create `references\search-strategy.md`

- [ ] Step 1：写故障定位场景的「先查诊断树」检索流程（2.A），含 `生产问题速查.md` 读取命令。
- [ ] Step 2：写普通任务场景的分层 grep 策略（2.B），仓→域→全 wiki 三层 + 触发条件。
- [ ] Step 3：写任务类型→目标 §节映射表（8 行，对照第 3 节 Phase 2）。
- [ ] Step 4：给出真实可跑的 grep 命令（PowerShell `-Encoding UTF8` + Git Bash 两版）：宽检索 + 节定向 + 关键词限范围。
- [ ] Step 5：写「结果太多时如何收窄」指引。
- [ ] 核验：以 `fms-gateway`（NP_FMS）和 `fabusurfer`（old_project，含生产问题速查.md）各干跑一个检索，确认命令正确输出。

### Task 3：任务处理框架（task-framework.md）

**Files:** Create `references\task-framework.md`

- [ ] Step 1：展开 Phase 1 三问的完整提问清单（模糊时向用户确认的规则）。
- [ ] Step 2：写 Phase 2 执行顺序（故障场景 vs 普通场景分支逻辑）。
- [ ] Step 3：写 Phase 4「收敛到唯一根源」判定准则（已收敛 vs 未收敛的判定标准）。
- [ ] Step 4：写 Phase 5 改进建议 4 行格式规范。
- [ ] Step 5：给出端到端示例——以「NP FMS 车辆离线排查」为例走完 Phase 1-5（Phase 2 先查速查 → Phase 3 调用 `fms-diagnose` + `fms-log` → Phase 4 收敛根源 → Phase 5 输出建议+风险）。

### Task 4：排查工具调用指引（diagnostic-tools.md）【新增】

**Files:** Create `references\diagnostic-tools.md`

- [ ] Step 1：写 Phase 3 工具选择矩阵（任务类型 → 适用工具，参考第 3 节 Phase 3 表格）。
- [ ] Step 2：写 `/fms-diagnose` 调用指引：
  - 先 `--list` 查可用检查项（按 scope 分 common/np/psa）
  - 按现象选对应 check
  - 输出字段解读（status/headline/evidence/suggestions）
- [ ] Step 3：写 `/fms-log` 调用指引：
  - 港口→日志源对应关系（NP=k8s / PSA=Loki / NB=SSH）
  - 关键参数（`--module`, `--grep`, `--lines`, `--minutes`）
  - 先 `--list` 再实际查的工作流
- [ ] Step 4：写 `/cmdcap` 调用指引（适用场景 + 正确用法：cmdcap shell → 命令 → cmdcap save 的序列，禁止与命令拼 `;`）。
- [ ] Step 5：写 `gitnexus-*` 调用指引：
  - `gitnexus-debugging`：用于调用链追踪、错误根源定位
  - `gitnexus-exploring`：用于理解陌生模块执行流
  - `gitnexus-impact-analysis`：配合 Phase 5 R4（依赖风险）使用
- [ ] 核验：以「fms-gateway 接口 500」场景，列出应调用哪些工具（顺序和命令示例），确认不遗漏关键工具。

### Task 5：风险清单模板（risk-checklist.md）

**Files:** Create `references\risk-checklist.md`

- [ ] Step 1：写 R1-R8 八个风险方向（对照第 3 节 Phase 5.2 表格）。
- [ ] Step 2：每个方向 3 个检查点 + 「辅助工具」列（wiki §节 / fms-diagnose / gitnexus-impact-analysis 等）。
- [ ] Step 3：写高/中/低/不适用的标注规则。
- [ ] 核验：以「修改 `fms-core` 共享库 `JobOrderCacheManager` 的 Redis key 格式」场景填写清单，验证 R4（依赖，`gitnexus-impact-analysis` 辅助）和 R1（兼容性，wiki §4 辅助）能被识别为高风险。

### Task 6：填充 SKILL.md 正文

**Files:** Modify `SKILL.md`

- [ ] Step 1：填充「触发时机」——DA 判定规则（需要 vs 不需要调用的场景各 4-5 条）。
- [ ] Step 2：填充 Phase 1（三问框架，简洁，引用 `task-framework.md`）。
- [ ] Step 3：填充 Phase 2（故障 vs 普通两条路径核心要点；grep 命令示例直接内嵌 3 个；引用 `search-strategy.md`）。
- [ ] Step 4：填充 Phase 3（工具选择矩阵概要 + 每种工具 1-2 行核心调用，引用 `diagnostic-tools.md`）。
- [ ] Step 5：填充 Phase 4（收敛准则：能说出「根源在 X 的 Y，原因是 Z」才算收敛）。
- [ ] Step 6：填充 Phase 5（4 行建议格式 + R1-R8 风险清单表；引用 `risk-checklist.md`）。
- [ ] Step 7：填充「评估闭环」（export-session D2 是外部评估机制；D2 报告中 wiki-search 触点的引用准确性是迭代输入；迭代路径：误命中 → 分析是关键词/§节/工具选择问题 → 更新对应 references/ 文件）。
- [ ] 核验：SKILL.md 自足可读（不打开 references/ 也能执行主流程）；Phase 2 和 Phase 3 均有可直接复制的命令示例。

### Task 7：安装 + 干跑验收

**Files:** Install skill

- [ ] Step 1：拷贝 `D:\jk_file\skills\wiki-search\` → `C:\Users\admin\.claude\skills\wiki-search\`。
- [ ] Step 2（干跑验证 1 — 故障定位场景）：
  - 输入：「NP FMS 有一辆车长时间离线，任务一直分配不出去」
  - 期望 Phase 1：主体=NP FMS 车辆离线；Why=生产故障；What=找到根因
  - 期望 Phase 2.A：先读 `D:\wiki\NP_FMS\fms-server\生产问题速查.md`（若存在）→ 在「车辆离线」或「任务分配失败」现象根找候选根因；再读 `fms-vehicle-bridge/architecture.md` §1/§6
  - 期望 Phase 3：调用 `fms-diagnose --port np --check vehicle-online` 取证
  - 期望 Phase 4：根源陈述锚定到具体组件/配置（如 `RedisNsMessageProducer` / Redis Stream 断连）
  - 期望 Phase 5：R3（性能）/R8（已知问题）等风险评估
- [ ] Step 3（干跑验证 2 — 改动影响评估场景）：
  - 输入：「需要修改 `fms-core` 的 `VehicleAlarmUtils` 告警格式，评估影响」
  - 期望 Phase 2.B：分层 grep → `fms-core/architecture.md` §3（`util/VehicleAlarmUtils`）和 §5（被哪些模块引用）
  - 期望 Phase 3：`gitnexus-impact-analysis`（`target: VehicleAlarmUtils, direction: upstream`）
  - 期望 Phase 5 R4：依赖风险=高（fms-core 共享库，波及多模块）
- [ ] Step 4（export-session 评估计划）：下次用本 skill 完成真实任务后，触发 `export-session`，检查 D2 报告：
  - 是否检测到 wiki-search 产生的 wiki 触点（Read/Grep `D:\wiki\...`）
  - 工具调用（fms-diagnose/fms-log 等）是否出现在 D1 维度
  - wiki 引用准确性（正确 / 幻觉 / 误解）
  - 记录评估结果到 `export-session-eval-log.md`，作为第一轮迭代输入

---

## 7. 未来规划（阶段二）

整体功能成型、经 `export-session` 评估稳定后：

1. **服务化**：封装为 Multica 上独立 agent（独立运维支持账号）
2. **Issue 化运维**：每次分析自动创建 Multica issue，记录 Phase 1-5 完整链路（任务认知 / wiki 检索命中 / 工具证据 / 根源陈述 / 改进建议 / 风险清单）
3. **可追溯**：团队可通过 issue 了解全链路细节
4. **反馈循环**：issue 评论补充/纠正 wiki 引导准确性，反哺 wiki 改进（via `/wiki-refine`）

---

## 8. 验收标准（DoD）

- [ ] SKILL.md 触发后，agent 完整走过 Phase 1-5，每阶段有明确输出物
- [ ] 故障定位场景下，Phase 2 先读 `生产问题速查.md`，再读架构文档
- [ ] Phase 2 检索引用明确路径（`D:\wiki\...\文件#§N`），不转述
- [ ] Phase 3 按任务类型正确选择工具（故障→fms-diagnose；日志→fms-log；远程命令→cmdcap；代码链路→gitnexus）
- [ ] Phase 4 输出唯一根源陈述
- [ ] Phase 5 风险清单覆盖 R1-R8，高风险项有缓解措施，工具辅助列完整
- [ ] 两个干跑场景输出符合期望
- [ ] `export-session` D2 能检测到 wiki-search 产生的 wiki 触点
- [ ] 绝不修改 `D:\wiki\` 任何文件

---

## 9. 全局约束

- **只读**：wiki-search 纯消费侧，绝不写 `D:\wiki\`；排查工具也全部只读
- **复用引擎**：域解析走 `wiki_engine resolve-domain`，不重造
- **直接引用**：Phase 2 输出必须是原文片段 + 路径，拒绝凭记忆转述
- **编码安全**：PowerShell grep 用 `-Encoding UTF8`；Python 用 `-X utf8`

---

## 10. 自查表

- **覆盖新增需求**：DA（评估 wiki 需要 → 触发）→ §4 触发判定；DB（故障优先诊断树）→ Phase 2.A；DC（直接引用）→ 各阶段输出物规格；DE（排查工具）→ Phase 3 + Task 4 + diagnostic-tools.md
- **工具覆盖完整**：cmdcap / fms-diagnose / fms-log / gitnexus-debugging / gitnexus-exploring / gitnexus-impact-analysis 全部覆盖，每种工具有适用场景 + 核心命令示例
- **文件结构更新**：新增 `diagnostic-tools.md`；Task 4 专门负责
- **两个干跑场景**：故障定位（车辆离线）+ 改动影响评估（共享库改动），覆盖两条主路径
- **已知边界**：若 `生产问题速查.md` 未为该仓创建 → Phase 2.A 直接跳到架构文档；若 gitnexus 未 index 当前仓 → 先跑 `npx gitnexus analyze` 再查询
