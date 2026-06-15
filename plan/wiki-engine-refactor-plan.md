# wiki-refine 工程化改造方案(wiki-engine)

> 状态:**v1.3 — 在 v1.2 上把 §6.5 / §7.1 的 promote 示例对齐运营默认(详见下行),仍可进入实现(A→D)**(修订 2026-06-15;定稿 2026-06-05;创建 2026-06-04)
> 范围:本次实施 A→D 四阶段;E(document-systems 接入)与 F(存量治理执行)留后续会话
> 配套讨论记录:本文档由 brainstorming + 双 Plan agent 设计稿收敛而来,所有"实测"均来自 D:\wiki 与 D:\jk\_file\skills 真实文件
> v1.3 修订(2026-06-15):§6.5 S4 示例 + §7.1 2.5.b 门禁样张的 `level` 由 `global` 改 `repo`(写 `<DOC_ROOT>\_common\`、前缀 `../_common/`),与 §13 决策 #1"当前一律 repo"对齐,消除"示例教 global、默认却是 repo"的歧义;§5 A1 放置阶梯补"默认级别"硬条款;global 两级路径机制降为 §6.5 注里一行。
> v1.2 修订(2026-06-15):① §5 / §7.1 1.0.b / A6 检查 13——安装根改"探测式解析"(去 `C:\Users\admin\` 硬编码,适配 codex / trae-cn 与换机 / CI);② §6.5 步骤 2——钉死"按内容寻址句柄对 baseline 快照解析";③ §6.3——补 `q_` 临时把手与显式持久 ID(PD-LIN 式)的关系。

***

## 1. 背景与问题

`/wiki-refine` 目前用一个 prose prompt 让 refine subagent 同时做四件事:源码追踪、gap 分析、**机械化改文档**、prose 自检。机械步骤靠 LLM 自觉执行,导致不稳定。实际后果已在 D:\wiki 现身(实测):

- `fabusurfer/port-data/architecture.md`、`port-ingest/architecture.md` 长出违反契约的 `## 11.` 章节;
- `port-data/lineage-open-questions.md` 是违反 wiki-principles §7 的派生问题文件;
- §10 闭环时"该删的不删、该并入正文的没并入"(问题 A-1);
- 跨模块同一事实在多处详写,无 owner、无引用收敛(问题 A-2);
- "所有系统共享内容"无契约、无维护流程:`D:\wiki\_common\` 已建但空,`fabusurfer/global/coordinate-heading-terms.md` 是自发雏形(问题 B)。

**改造方向**:把可确定化的部分(解析、校验、结构变更)做成确定性 Python 引擎,由 code agent(claude code / codex)驱动;LLM 只保留语义判断(场景分类、全解/部分解、owner/级别归属、中文撰写)。修改场景枚举为 S1–S8,每类映射固定的引擎事务形态,违规操作被引擎**硬拒绝**。

## 2. 已锁定决策(用户已确认)

| # | 决策        | 内容                                                                                                                                                                                |
| - | --------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1 | 两级 common | 全局 `D:\wiki\_common\`(跨仓库)+ 仓库级 `<DOC_ROOT>\_common\`(仓内子系统共享)。D:\wiki 是单一 git 仓,两级都在工作树内,相对链接可达:子系统文档→仓库级 `../_common/x.md`、→全局 `../../_common/x.md`                             |
| 2 | 工程化边界     | 引擎 = 解析 + 不变量校验(lint)+ 原子结构算子,违规硬拒绝;agent = 场景分类 + 内容撰写                                                                                                                           |
| 3 | 组织        | 一个共享引擎(`document-systems/scripts/wiki_engine/`),技能变薄(场景 playbook + 对话编排),**不**新建 common skill                                                                                     |
| 4 | common 类型 | 锁定 4 类:glossary(术语表)/ shared-lib(共享库契约)/ protocol(公共协议)/ infra(基础设施约定),不设"其他"                                                                                                     |
| 5 | 读源边界      | 轻量文档(common + 辅助文档)可跨子系统读本仓源码、止步 jar/SDK;严格文档(子系统 architecture.md)仍只读本子系统。**升级机制**:subagent 判断需读禁区 → 返回 escalation 请求 → 主 agent 询问用户 → 同意后扩大范围重派。升级只扩大"读",不改变"写"的归属规则             |
| 6 | 本次范围      | A→D;E、F 后续会话                                                                                                                                                                      |
| 7 | 目录命名空间    | `_` 前缀目录是**非业务命名空间**,永不与真实仓库/子系统名冲突:`_common\`=引擎管理的公共文档(light 契约);其它 `_*\`(如已存在的 `_meta\`,放 gitnexus 等工具/过程笔记)=引擎忽略的保留区。业务 wiki 仓 = 不以 `_`/`.` 开头的顶层目录。两级 common 目录定名 `_common\` |

## 3. 总体架构

```
┌─ 技能层(prose,薄)────────────────────────────────┐
│ wiki-refine:对话编排 + 场景分类(playbook)+ 用户门禁   │
│ document-systems:生成流程(本次只动模板/契约)          │
├─ 契约层(references/,单一事实源)───────────────────┤
│ wiki-principles / code-wiki-conventions /              │
│ common-conventions(新)/ scenario-playbook(新)      │
│ templates/(root + 4 个 common 模板)                  │
├─ 引擎层(scripts/wiki_engine/,Python 3.8+ stdlib)────┤
│ 解析(容忍漂移)→ lint(规则引用契约条款)→             │
│ 事务算子(原子、lint 增量否决、硬规则)                  │
└──────────────────────────────────────────────────┘
```

**目录命名空间(WIKI\_BASE 顶层,引擎第一道工序:目录归类)**:在按 DocKind 细分文档之前,引擎先对顶层目录归类——`_` 前缀划出"非业务"命名空间,使其永不与真实仓库/子系统名冲突。

| 类别          | 判别                                                            | 例子                                                 | 引擎如何管                                                                                                          |
| ----------- | ------------------------------------------------------------- | -------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| 业务 wiki 仓   | 不以 `_`/`.` 开头的顶层目录                                            | `fabusurfer`、`fms-server`、`charge-manage-platform` | 按 strict 契约治理(再经 DocKind 细分)                                                                                   |
| 引擎管理的公共命名空间 | 恰为 `_common`(全局 `D:\wiki\_common\`、仓库级 `<DOC_ROOT>\_common\`) | `_common\`                                         | light 契约;`promote_to_common`/`init-common`/`questions`/light-lint 作用其上;被业务文档 `../_common/`、`../../_common/` 引用 |
| 引擎忽略的保留区    | 其它 `_` 前缀目录                                                   | `_meta\`(gitnexus 笔记等工具/过程文档)                      | 不 lint、不碰、不要求契约;自由区                                                                                            |

`.` 开头的目录(`.git`/`.idea`/`.claude`)一律跳过。仓库内同理:`<DOC_ROOT>` 下 `_common` = 仓库级 common,其它 `_*` = 忽略,其余 = subsystem 目录。`_common` 与 `_meta` 的区别 = "引擎管(需契约、被引用)"对"引擎不管(自由笔记)"。

**文档三分类(DocKind)**:

| 类别      | 范围                                                                                            | 规则集                                                                                             |
| ------- | --------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| strict  | 子系统/单系统 `architecture.md`、根文档                                                                 | 完整契约(§1–§10 / 根文档具名区域,见 §6.7)                                                                   |
| light   | `_common` 文档 + `<子系统>/<topic>.md` 辅助文档                                                        | frontmatter + 统一 `## 待确认 / 疑问` 章节 + 锚点格式 + 无臆测词 + 标识符原样;**不**施加 §1–§10                          |
| ignored | `_meta\` 等非 `_common` 的 `_*\` 目录、`issue/**`、`whole_architecture.md`、`spec/**`、`**/.review.md` | 顶层 `_*`(非 `_common`)由目录归类直接忽略;仓内路径 allowlist 写死在 common-conventions.md 的 fenced block,引擎读取;均不校验 |

**关键现实约束(实测,实现全程不可违背)**:

### 约束 1 — 标题按位置+编号识别,锚点必须复刻 GitHub slug 算法

§1 标题一半文档写的是"概览"、一半是"概述"(实测 `port-data`、`port-service` 等是"概览")。所以契约**按位置+编号**识别章节(§1、§6.6),不按字面标题;`STRUCT_TITLE_CANONICAL` 这类标题字面校验只报 INFO、永不阻塞;引擎**永不改写标题**。

而\*\*锚点(anchor)\*\*必须从实际标题用 **GitHub-exact slugger** 计算。锚点是 markdown 自动给标题生成的跳转 id,跨文档链接靠它定位。算法(以实测标题 `### 6.6 OTA / 版本 / 文件日志流` 为例):

1. 转小写:`6.6 ota / 版本 / 文件日志流`
2. 删非字母数字空格连字符(`.`、`/` 被删,但 `/` 左右两个空格留下):`66 ota  版本  文件日志流`
3. 空格转连字符(那两个空格 → 双连字符 `--`;CJK 原样保留):`66-ota--版本--文件日志流`

最终锚点 `#66-ota--版本--文件日志流`。这不是人手输入的,是机器算的;它已在你的真实 wiki 里被用上——`port-vehicle/architecture.md` 第 116/131/309 行就有 `[port-device § 6.6 …](../port-device/architecture.md#66-ota--版本--文件日志流)`。

**为什么引擎必须复刻它**:(a) 校验跨文档链接是否指向真实标题(`LINK_ANCHOR_RESOLVES`);(b) `move_with_reference`/`promote_to_common` 时自动生成新引用链接。两者都要求精确复刻,连 `/` 产生双连字符这种怪例都要算对,否则生成死链。故 `slug.py` 是"唯一事实源",配黄金测试表(这个真实例子是其中一例)。

### 约束 2 — 外科手术式字节拼接,禁止整文档重排

渲染必须是**外科手术式字节拼接**:解析时给每个节点记录 `(start_offset, end_offset)`,改某节点时**只替换它那一段字节(span)**,其余字节原封不动。禁止"重新生成整个文档"式重排。`render(parse(x)) == x` 字节级成立是 B 阶段第一道门禁。否则:改一行子系统,diff 却显示整文档变了(如把"概览"顺手改成"概述"),git diff 噪声爆炸、lint 增量(只看新引入的违规)失真。

### 约束 3 — 根文档比模板脏,只动具名区域、其余字节原样

你的 `fabusurfer/architecture.md`(根文档)实测比模板多出几处**漂移**(模板里没有的):

- 开头 YAML frontmatter `--- whole_architecture: ./whole_architecture.md ---`(code agent梳理时加的指针);
- `## 系统架构特点`(第 97 行,模板无此章节);
- `## 6. port-data 报表数据链路补充`(第 156 行,根文档本不该有带编号的 §章节,非法漂移)。

引擎对此的三层处理:

- **解析容忍**:遇到这些多出来的章节不报错、照常解析成结构树;
- **lint 报告**:把它们列为发现项报告(让你知道),但因是存量、非本次引入,**不阻塞**操作;
- **`update_root`** **只动具名区域,其余字节原样**:改根文档(加子系统行、连依赖边等)时**只碰那 4+1 个具名区域**(子系统清单表 / 依赖关系图 / 跨系统通信方式 / 辅助资源 / 仓内公共文档),**绝不碰** YAML frontmatter、`系统架构特点`、那个非法 `## 6.`。

**为什么**:根文档里有人手工加的、模板不认识的宝贵内容。走"按模板重新生成"会整段抹掉它们;外科手术式只动具名区域,既维护结构化区域、又不误伤人工内容。

### 约束 4 — 同样的 `## 11.`,strict 非法、light 合法,由 DocKind 决定

对比两个真实文件:

| 文件                                  | 章节体系                                                               | `## 11.`          |
| ----------------------------------- | ------------------------------------------------------------------ | ----------------- |
| `port-data/architecture.md`         | 严格 §1–§10 子系统契约(strict)                                            | **非法**(契约禁止 §11+) |
| `port-device/alarm-architecture.md` | 自成一套:§1 概述 / §2 功能需求 / … / §10 待确认与优化建议 / **§11 附录:代码锚点索引**(light) | **合法**            |

`alarm-architecture.md` 不是子系统契约文档,而是专题/辅助文档(light),用完全不同的章节方案。"禁止 §11+"只管 strict 文档。

**为什么引擎必须先分 DocKind**:若对所有 `.md` 一刀切套"禁止 §11+",会把 `alarm-architecture.md` 合法的 `## 11. 附录` 误报。所以引擎第一步先判 DocKind:`port-data/architecture.md` → SUBSYSTEM(strict)→ 禁令生效、抓出非法 §11;`alarm-architecture.md` → ANCILLARY(light)→ 禁令不适用、放行。**同样语法、不同判决,取决于 DocKind**——这是"文档三分类"作为引擎第一道工序的原因。

## 4. 修改场景枚举 S1–S8(方案核心,对应问题 A/B)

> **用户门禁字母图例**(沿用 wiki-refine 现有交互约定,下表"用户门禁"列引用):
>
> - **A 组 diff 门禁** **`A/R/E`**(审阅本轮 subagent 整体改动,现行 Phase 2.4):**A**=Accept 接受改动进入下一步;**R**=Rollback `git restore` 回滚整轮、回到本轮开头;**E** `<反馈>`=带反馈让 subagent 重做同一话题。
> - **B 组 逐条建议门禁** **`A/S/R`**(逐条审阅"建议",现行 Phase 2.5 / 新增 2.5.b 公共化):**A**=Apply 应用这一条;**S**=Skip 跳过但记入对应子系统 §10 留档;**R**=Reject 既不应用也不留档。
> - 注意 **R 含义随组不同**:A 组的 R=回滚整轮改动,B 组的 R=拒绝这一条建议。
> - 新增 **2.4.b escalation 门禁**(读源越界请求,仅两键):**A**=允许扩大读取范围并重派;**R**=拒绝(缺口落 §10)。

| ID               | 触发信号                                        | agent 的分类判断                                       | 引擎事务形态                                                                                                                       | 用户门禁                                          |
| ---------------- | ------------------------------------------- | ------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------- |
| **S1** §10 全解    | 既有 §10 条目被追踪结果/用户补充完全回答,无残余未知               | "条目的**每一个**子句都闭环了吗?"有残余 → S2                      | `resolve_question(full)` + 同事务耦合 `update_section`(把结论写进正文对应章节)。**引擎强制耦合**:删 §10 条目而不补正文 → 硬拒绝(也可提供 existing-anchor 证明结论已在正文) | 现有 A/R/E                                      |
| **S2** §10 部分解   | 部分子句闭环,部分仍未知                                | "哪些闭环、哪些保留?残余如何重新表述?"                             | `resolve_question(partial, 残余重写文本)` + 已确认部分 `update_section`                                                                 | A/R/E                                         |
| **S3** 同一事实多文档详写 | 追踪发现同一内部事实在 ≥2 个文档详细出现                      | "owner 是谁?"指南:定义该事实的 `Class#method` 所在子系统 = owner | `move_with_reference`:owner 保留详写,其余替换为锚点引用 + 一句概述                                                                            | A/R/E                                         |
| **S4** 跨系统共享事实   | ≥2 子系统需要、无单一属主(术语/共享库/协议/基础设施)              | 放置阶梯(见 §5 A1)定级别+类型                               | `promote_to_common(level, type)` + 各处 `move_with_reference` 改引用,scaffold 目标 common 文档(如不存在),**全原子**                          | **新增公共化门禁 A/S/R**(S=暂不公共化,相关子系统 §10 记"建议公共化") |
| **S5** 新增已验证事实   | 追踪发现未记录的、可代码验证的事实                           | "归哪个章节?数据名可 grep 吗?"                              | `update_section`(引擎 lint 管住六渠道、§6↔§7 一致)                                                                                     | A/R/E                                         |
| **S6** 新增不确定点    | 链路未闭环/生产方未知/边界模糊                            | 按 `[§<位置>] …。已检查:…。建议核实方向:…` 表述                   | `add_question`(引擎校验 §10 格式)                                                                                                  | A/R/E                                         |
| **S7** 用户口述知识    | `<USER_SUPPLEMENT>` 含 jar/SDK 内部、运行时配置、业务规则 | "归哪个章节?与代码可验内容分段"                                 | `update_section` 带 `> 来源:用户口述(日期)`(数据名豁免 grep 但必须带标注)                                                                        | A/R/E                                         |
| **S8** 根文档影响     | 子系统清单缺行/依赖边错漏/协议缺行/辅助资源漂移/公共索引缺行            | "哪个根工件?构造精确的行/边"                                  | subagent 返回现成 `update_root` payload;主 agent 经用户确认后**用引擎应用**(替代现行手工 Edit)                                                     | 现有根门禁 A/S/R,改为引擎执行                            |

**横切规则**:

- 一个话题可命中多场景 → 合成**一个事务**,先 `--dry-run` 自修复到干净,再真实 apply(原子:全成或全不成);
- owner / 级别 / 全解 vs 部分解是 **agent 的语义判断**,引擎只校验结构化结果;
- **escalation**:R1 追踪命中禁区(他子系统源码 / jar / SDK / 他仓)且确有必要 → 先完成不依赖禁区的部分,返回 `escalation_request{zones:[{kind, target, reason}]}`(schema 见 §7.2 示例) → 主 agent 询问用户 → 同意则带 `<EXPANDED_SCOPE>` 重派,拒绝则缺口落 §10。经授权读 jar/SDK 得来的内容标注 `> 来源:经用户授权阅读 <对象>(YYYY-MM-DD)`,优先落 shared-lib 类 common 文档。

## 5. 阶段 A — 契约文件 + 场景 playbook

全部在 `D:\jk_file\skills\document-systems\` 下。**安装根不再硬编码**:wiki-refine 运行时按下述顺序探测、取第一个存在者得到"安装根",再以其绝对路径引用引擎与契约文件(展开后形如 `C:\Users\admin\.claude\skills\document-systems\...`,但该字面是解析结果、非写死):

1. **仓内解析**(优先,对 codex / trae-cn 友好):能定位本仓(`git rev-parse --show-toplevel` 命中且 `<repo-root>\document-systems\` 存在)→ 安装根 = `<repo-root>\document-systems`。wiki-refine 与 document-systems 本是同仓兄弟目录,以仓库为工作目录的 code agent 直接命中;
2. **Claude Code junction**:否则用 `~/.claude/skills/document-systems`(展开 `%USERPROFILE%`,不写死 `admin`);
3. **配置覆盖**:否则读可选配置项指定的安装根;
4. 三者皆无 → 现有中文中止(契约文件缺失)。

如此同一份 SKILL.md 不改字面即可在 Claude Code / codex / trae-cn 下运行,且换机、换 Windows 用户、CI / 容器、非 Windows 均不失效(原 `C:\Users\admin\...` 硬编码会在这些场景断)。MAINTAINER §3 的约束相应从"只用绝对路径"改为"安装根按上述顺序解析,绝对路径是其展开结果"(见下文 A6 检查 13)。

**A1 新建** **`references/common-conventions.md`**(agent-facing 英文):

- 两级语义 + 引用路径规则(决策 1);
- **放置判定阶梯**:① 事实归单一子系统所有 → 留在该子系统文档,他处引用;② 本仓 ≥2 子系统共享且无单一属主 → 仓库级 common;③ 确有第二个仓库消费或全公司标准 → 全局 common。宁低勿高;拿不准 → 仓库级 + 记"建议全局化"待确认条目;**默认级别**:除非命中 ③,promote 的 `level` 一律 `repo`(引擎缺省值),采用 `global` 须在 2.5.b 公共化门禁显式标级别并经用户确认(§13 决策 #1);
- 4 类 common 文档轻量结构(各含统一尾章 `## 待确认 / 疑问`,条目格式同 wiki-principles §5 → 引擎 `questions` 可全 wiki 枚举);frontmatter:`common_type` / `level: repo|global` / `owns: <事实稳定id>`;文件名 kebab-case 英文;
- **`_common`** **组织模型(已定)**:**4 类为轴 + 类内薄骨架 + index 导航**——
  - **薄骨架**:每份 common 文档保留 3 个固定小节(`## 1. 范围与级别` / 类型主体 / `## 待确认 / 疑问`),**骨架内正文随意写**。这层薄骨架是"查得动"的代价:统一 `待确认/疑问` 让引擎 `questions` 能把 common 未决项与子系统 §10 一起枚举;可预测小节标题让 `../../_common/x.md#锚点` 引用稳定。**不允许"完全无结构"**(否则 `questions`/锚点失效、退回自发雏形的混乱)。
  - **文档粒度**:一份文档 = 一个连贯主题簇(如 `coordinate-heading-terms.md` 收一组坐标/航向术语);index 列到**文档级**,文档内找具体某条靠锚点/grep。非"一术语一文件"(碎),非"一类一大文件"(臃肿)。
  - **查询两层**:① **发现/导航**(有哪些共享文档)靠 `index.md`,按 4 类分组,**极简**——每条仅 文件/级别/一句话/`owns`,**不复述内容**(避免成为会漂的派生文件);② **跨文档查询**(列全部未决疑问、谁引用某文档/术语)靠引擎实时算(`questions`/`refs`/grep),**不进 index**(wiki-principles §7 native-tools-first)。
- Ownership 扩展:common 文档拥有共享事实,子系统文档必须锚点引用、不得复制内部细节;
- **读源边界阶梯 + escalation 条款**(决策 5 全文);
- **ignore-globs fenced block**(引擎读取):`issue/**`、`whole_architecture.md`、`spec/**`、`**/.review.md`。

**A2 新建** **`references/scenario-playbook.md`**(agent-facing 英文):§4 的 S1–S8 表 + 三个判断指南(owner 归属 / common 级别阶梯 / 全解 vs 部分解)+ 横切规则 + escalation 流程。

**A3 新建 4 个模板** `references/templates/common-{glossary,shared-lib,protocol,infra}.md`:frontmatter + `## 1. 范围与级别` + 类型主体(glossary:术语表格;shared-lib:对外契约/调用面 + 使用方,禁库内部细节;protocol:协议定义 + 生产方/消费方;infra:约定 + 适用范围)+ `## 待确认 / 疑问`。**引擎 scaffold 从这些文件读取,引擎包内不复制模板(单一来源)**。

**A4 修改** **`references/templates/root-architecture.md`**:在 `## 数据资产索引指引` 与 `## 辅助资源` 之间新增固定章节 `## 仓内公共文档`(含 `<REPO_COMMON_INDEX_ROWS>` 占位 + 指向 `./_common/` 与全局 `../_common/` 的固定文案)。

**A5 微调共享契约**(遵守 MAINTAINER §1 规则不丢 / §2 领域中立):`wiki-principles.md` §3 加一句领域中立的"共享事实由指定 owner 文档拥有,他处引用不复制";`code-wiki-conventions.md` 加一行指针(common 文档 attribution 遵循其 §3)。

**A6 修改** **`MAINTAINER.md`**,新增检查 10–15:

- **10 引擎↔契约对齐(双向完备性审计)**:契约(prose)是单一事实源,引擎 lint(代码)是执行者,二者必须双向绑死、可审计,防止漂移。
  - **方向 A——每条 lint 规则引用契约条款**:引擎里每条规则注明出处(`rule-catalog` 输出携带)。例:`Q10_FORMAT` → `wiki-principles §5`;`ANCHOR_NO_LINENO` → `wiki-principles §2`。拦截:有人加了条"表格不准超 20 行"但无任何契约这么写 → 不通过 → 要么写进契约要么删规则(**引擎不能发明契约没有的约束**)。
  - **方向 B——每条"机械可检"的契约条款,要么有引擎检查、要么显式标** **`LLM-only`**:机器能查的必须有对应 lint;确实需语义判断的明确标 `LLM-only`,说明"此处没有引擎规则是故意的,不是漏掉"。例(有规则):`code-wiki-conventions §8`「数据名源码可 grep」→ `DATA_NAME_GREP`。例(标 LLM-only):`wiki-principles §3` ownership 里"判断是跨系统契约还是内部实现泄漏"机器做不了——引擎只机械标信号("出现别的子系统标识符"),裁决留给 review LLM,故该条标 `LLM-only`/hybrid。拦截:契约新增"§5 上游按字母序"(机械)却无引擎规则、也没标 LLM-only → 不通过(**机械契约不能写了没人查**)。
  - 运维含义:**每次改契约都要配套过一遍引擎**,否则二者迟早对不上(对应本方案最大风险:prose 与代码双维护漂移)。
- 11 章节名常量对齐:引擎常量 = 模板/契约字面;§4 对齐集合扩展至 common 模板 + common-conventions;
- 12 引擎输出语言:英文 `rule_id`/`code` + `message_zh`;技能只对用户展示 `message_zh`;
- 13 wiki-refine **按 §5 探测顺序解析"安装根"**(仓内 → `~/.claude/skills` junction → 配置覆盖),再以其绝对路径调用引擎与新契约文件;**禁止把安装根写成 `C:\Users\<user>\...` 字面量**(机械校验 `SKILL.md` / `refine-subagent-prompt.md` 无此类硬编码),三者皆无则中文报错中止。此条把 §3"只用绝对路径"细化为"解析得到的绝对路径",保证 codex / trae-cn 等非 Claude Code agent 及换机 / CI 场景可用;
- 14 引擎测试全绿才可发布依赖它的技能改动;
- 15 MIGRATION.md 与引擎算子名/契约区域同步。

**A 门禁**:MAINTAINER §4/§11 对齐人工核查通过;新文件交叉引用有效。

## 6. 阶段 B — 引擎核心(Python 3.8+ stdlib-only,TDD)

位置 `document-systems/scripts/wiki_engine/`,fixtures 取材 D:\wiki 真实漂移样本。

### 6.1 模块结构

```
wiki_engine/
  cli.py        # argparse;JSON stdout;退出码模型
  io_utf8.py    # 强制 UTF-8 读写、BOM 剥离、临时文件+rename 原子写
  slug.py       # GitHub-exact slugger(唯一事实源,所有链接校验/生成必经)
  model.py      # Document/Section/Entry/AssetTable/Question/RootDoc/Link(含字节 offset)
  doc_kind.py   # SUBSYSTEM|ROOT|SINGLE|COMMON|ANCILLARY|IGNORED(路径+frontmatter+ignore-globs)
  parser.py     # 容忍漂移解析(YAML/blockquote 双 frontmatter、§11+、"概览"标题、额外子节)
  questions.py  # 稳定问题 ID(见 6.3)
  address.py    # 章节寻址(见 6.4)
  render.py     # 外科手术式字节拼接(只替换被改节点 span)
  lint/         # registry(规则:id/契约条款引用/severity/blocking/DocKind 范围)
                #   + structure/anchors/links/data_names/speculation/ownership/common_conv
  ops/          # update_section / resolve_question / add_question /
                #   move_with_reference / promote_to_common / update_root(+耦合规则声明)
  txn.py        # 加载→静态校验→内存应用→硬规则→lint 增量→全写或全不写
  refs.py       # 实时反向引用计算(不落任何索引文件)
  errors.py     # 退出码映射
tests/          # unittest + fixtures
```

### 6.2 CLI(payload 一律走文件,避免中文上命令行;`python -X utf8` 调用)

| 命令                                                                                 | 用途                                                |
| ---------------------------------------------------------------------------------- | ------------------------------------------------- |
| `outline --path <md>`                                                              | 解析结构树(章节/§6 入口/§7 表/offset),供 agent 寻址            |
| `questions --path <md\|dir> [--recursive]`                                         | 枚举 §10/待确认 条目(含稳定 ID),覆盖 strict + light 文档        |
| `lint --path <md\|dir> [--recursive --source-root <源仓根> --strict --rules <id,..>]` | 全量不变量校验,JSON 发现清单                                 |
| `apply --txn <json 文件> [--dry-run --source-root]`                                  | 原子多算子事务                                           |
| `init-common --level repo\|global --name <slug> --type <4类>`                       | 从模板 scaffold common 文档;全局层维护极简 `_common/index.md` |
| `refs --path <md> [--anchor --scope doc-root\|wiki]`                               | 实时反查:谁链接到该文档/锚点                                   |
| `rule-catalog`                                                                     | 输出完整 lint 规则表(id→契约条款→severity→blocking→范围)       |

### 6.3 稳定问题 ID

**要解决的问题**:agent 要让引擎"解决某条 §10 疑问"(S1/S2),得能精确指认是哪一条。用序号(第 2 条)很脆——删了第 2 条,第 3 条变第 2 条,序号全乱。所以 ID 从**内容**派生、不从位置。

**配方**:取三段,用分隔符 `‖`(内容里不会出现的符号)拼接,SHA1 取前 8 位十六进制,加前缀 `q_`:

`q_` + sha1(`doc相对路径 ‖ [§位置]规范化 ‖ 疑问首句规范化`)\[:8]

- **doc 相对路径**:这条疑问在哪个文档(如 `port-data/architecture.md`);
- **`[§位置]`** **规范化**:条目开头那个定位标签(去空格、NFC 归一);
- **疑问首句规范化**:`]` 之后到第一个 `。` 为止的"核心疑问"。`已检查:…`、`建议核实方向:…` **不进哈希**。

以 `port-data/architecture.md` 一条**真实** §10 为例:

```
- [§7.1 关系型数据库表] 多个 `@TableName` 未显式写 `value`,运行期表名依赖
  MyBatis-Plus 默认命名策略和 Nacos 数据源配置;…显式表名。
  已检查:`src/main/java/ai/fabu/data/common/model/entity/`、…。
  建议核实方向:运行环境 MyBatis-Plus 表名转换规则与真实数据库 DDL。
```

拆出哈希输入:路径 `port-data/architecture.md` ‖ \[§位置] `§7.1 关系型数据库表` ‖ 首句 `多个 @TableName 未显式写 value …显式表名`(`已检查`/`建议核实方向` 两段不参与)。

由此三条**性质**:

- **① 改"已检查/建议核实方向"不变 ID**:这两段在首句之后、不入哈希。S2 部分解决最常做的就是补一个已检查文件 / 重写建议核实方向,此时仍是**同一条疑问**,ID 不变 → agent 用原 ID 仍指得到它。这正是要的稳定性。
- **② 改** **`[§位置]`** **才换 ID(问题真的移动了)**:`[§位置]` 入哈希。若发现这条其实该挂 §6.3(数据交互)而非 §7.1,改 `[§7.1…]`→`[§6.3…]`,ID 随之变——**对的**,它锚到了不同章节、语义上已是另一条疑问,换 ID 反映"它移动了"。
- **③ 同文本不同文档 → 不同 ID**:路径入哈希。你的 `fms-core/architecture.md` §10 里**也有**一条几乎同主题的疑问(`@TableName` 未显式标注、表名取决于 MyBatis-Plus 驼峰转换);若不把路径放进哈希,两条会**撞成同一 ID**;放了路径,port-data 的与 fms-core 的各得各的 ID,agent 能无歧义指"port-data 那条"。

**为什么只取首句、不哈希整条**:整条含会变的"已检查/建议核实方向";只哈希"核心疑问(首句)+ 挂在哪(§位置)+ 哪个文档(路径)",才做到"日常细修不变、真正不同才变"。首句是"哪里不确定"(耐久本质),其余是"为此做了什么"(易变)。补充:agent 每轮用 `questions` 现取当前 ID 列表,故偶尔改首句导致换 ID 也不影响使用——稳定性保的是"一次会话内 + S2 常见细修",不当永久主键。

**与显式持久 ID 的关系(如 MIGRATION M2 的 `PD-LIN-001..009`)**:`q_` 是会话内的临时把手——算出来、不落盘进 wiki、每轮 `questions` 现取,故"找得到问题"从不依赖它稳定(定位靠解析 §10,匹配不上即 `E_ADDR_NOTFOUND` 硬失败、绝不改错)。若某条 §10 需要**跨会话持久身份**(被别处长期引用、跨多次治理跟踪),应在条目里写**显式领域 ID**(如 `- [§7.1 …] PD-LIN-003:…`),由人手赋、文本细修不动它,这才是"永久主键"。两套 ID 互补:显式 ID 写在首句内,反而让 `q_` 哈希更稳(`PD-LIN-003` 这种 token 几乎不变)。引擎不强制显式 ID,仅在其存在时把它当作首句的一部分纳入哈希。

### 6.4 章节寻址

算子用 `at` 块指定"改文档的哪个位置",**纯结构寻址、永不用行号**(行号会随提交漂移)。字段:

- `section`:顶层章节号,如 `"6"`、`"7"`(必填);
- `entry`:§6 入口,两种写法——编号 `"6.6"`(精确)或标识符子串 `"OTA"`(匹配 §6 下标题含该 token 的唯一入口);
- `subsection`:`"处理流程"`/`"数据交互"`(§6 入口下的 H4 子节)或 `"7.3"`(§7 某张反查子表);
- `anchor_mode`:`replace`(替换该节点正文 span)/ `append`(在该节点正文末尾、下一个标题前插入)/ `append_table_row`(向表格追加一行,校验列数=表头)。

拒绝:命中 0 个 → `E_ADDR_NOTFOUND`;`entry` 用标识符子串命中 ≥2 个 → `E_ADDR_AMBIGUOUS`(要求改用编号形式)。

**例 1**——向 port-data §7.1 关系型数据库表追加一行(表头 `| 表名 | 主键/关键索引 | 读取的入口 | 写入的入口 |`):

```json
{ "section": "7", "subsection": "7.1", "anchor_mode": "append_table_row" }
```

配套 payload 文件(一行,列数须=4):`| \`dws\_vessel\_job\` | — | 工班报表接口 | port-ingest 宽表同步 |\`

**例 2**——向 port-device §6.6 OTA 入口的"数据交互"子节末尾补一段:

```json
{ "section": "6", "entry": "6.6", "subsection": "数据交互", "anchor_mode": "append" }
```

`entry` 也可写 `"OTA"`,只要 §6 下仅一个标题含 OTA;否则 `E_ADDR_AMBIGUOUS`,改回 `"6.6"`。

**例 3**——move/promote 把某段替换为引用链接,需 `replace_match_file` 与现文**字节匹配**(不匹配 → `E_MATCH_STALE`,防基于陈旧内容误改):

```json
{ "section": "6", "entry": "6.6", "subsection": "数据交互", "anchor_mode": "replace" }
```

另带 `replace_match_file`(现状原文)+ `reference_text_file`(替换后的 `[X § 章节](../...#锚点)` 引用)。

### 6.5 事务语义(核心)

1. 加载所有 target 文档,逐文档记录 lint **基线**;
2. 各 op 静态校验(schema、寻址可解析、字节匹配、耦合存在);**按内容寻址的句柄(`question_id`、`replace_match_file`)一律对加载时的 baseline 快照解析**——`question_id` 用 `questions.py` 按"未施加任何本事务 op"的原始内容重算 ID 匹配,绝不用被前序 op 改过的中间态;否则同一事务"先 `update_section` 改了 §10 首句、后 `resolve_question` 拿旧 `q_`"会扑空(`E_ADDR_NOTFOUND`)。这与第 3 步"op 间重算 offset"不冲突:offset 是字节位置、随应用推进而变,id 匹配的是语义身份、锚定 baseline;
3. 按序内存应用(span 替换,op 间重算 offset);
4. **硬规则**(无视基线,恒拒绝):向 strict 文档引入 §11+;`resolve_question(full)` 无耦合 body 编辑或有效 existing-anchor 证明;新增指向派生文件的链接;
5. **lint 增量**:`新发现 = 后 − 前`,键为 `(rule_id, 结构位置, 消息hash)`(非行号);blocking 新发现 → 整体拒绝;**存量漂移不阻塞**(概览标题、未触及的旧 §11);
6. 提交:同目录临时文件 + rename,全写或全不写。`--dry-run` 走完 1–5,输出 diff 预览 + 发现,零写入。

**完整事务 JSON 示例(S1:§10 全解 + 耦合正文写入)**——把 port-data 一条"表名"疑问闭环:删 §10 条目、同事务把结论写入 §7.1:

```json
{
  "version": 1,
  "doc_root": "D:\\wiki\\fabusurfer",
  "source_root": "D:\\code\\fabusurfer",
  "intent": "S1: port-data §7.1 表名疑问已确认",
  "ops": [
    { "op": "resolve_question", "target": "port-data/architecture.md",
      "mode": "full", "question_id": "q_a1b2c3d4",
      "coupling": { "kind": "body_edit", "ref_op_index": 1 } },
    { "op": "update_section", "target": "port-data/architecture.md",
      "at": { "section": "7", "subsection": "7.1", "anchor_mode": "append_table_row" },
      "content_file": "payloads/s1_row.md" }
  ]
}
```

- `coupling.kind=body_edit, ref_op_index=1` 指向同事务第 2 个 op(0 基)——这就是"删 §10 必须有正文落点"的硬绑定;删掉第 2 个 op,`resolve_question(full)` 直接退出码 5(`E_COUPLING_MISSING`)。
- 另一种 `coupling.kind=existing_anchor` + `{ "anchor": "port-data/architecture.md#7-数据资产" }`:证明结论已在某锚点、无需新写,引擎校验该锚点可解析且内容已在。
- 中文 payload 走文件(`s1_row.md` 内容即例 1 那一行),不上命令行。

**完整事务 JSON 示例(S4:promote\_to\_common)**——把 ego\_info 外部生产链路提取到仓库级 common,并把 port-data 的内联段改为引用:

```json
{
  "version": 1,
  "doc_root": "D:\\wiki\\fabusurfer",
  "intent": "S4: ego_info 外部生产链路提取到仓库级 common",
  "ops": [
    { "op": "promote_to_common", "level": "repo", "type": "shared-lib",
      "common_name": "ego-info-source",
      "title_file": "payloads/ego_title.md", "body_file": "payloads/ego_body.md",
      "sources": [
        { "target": "port-data/architecture.md",
          "at": { "section": "6", "entry": "6.6", "subsection": "数据交互", "anchor_mode": "replace" },
          "replace_match_file": "payloads/ego_pd_old.md",
          "reference_text_file": "payloads/ego_ref.md" }
      ] }
  ]
}
```

- `level=repo` → 写 `<DOC_ROOT>\_common\ego-info-source.md`(即 `D:\wiki\fabusurfer\_common\ego-info-source.md`,不存在则从 `common-shared-lib.md` 模板 scaffold);引用前缀按源文档深度算(子系统文档 → `../_common/`)。
- 每个 source 的 `replace_match_file` 须字节匹配现文,替换为 `reference_text_file` 的锚点引用;新 common 文档 + 全部被改 source 一起跑 lint 增量,任一引新违规 → 整体回滚。
- 注:此例用 `level=repo`(运营默认,见 §13 决策 #1;promote 的 `level` 缺省即 `repo`)。`level=global` 仅路径不同——写全局 `D:\wiki\_common\`、引用前缀 `../../_common/`(两级上溯);`level` 字段照常支持 global,待真实跨仓消费再传 `global` 上移。

**lint 增量怎么判(承接步骤 5,以上面 S1 事务为例)**:port-data 当前**基线**已含 `STRUCT_NO_SECTION_11PLUS`(那个非法 §11)、`STRUCT_TITLE_CANONICAL`(概览,INFO)。该事务只动 §7/§10:

- 重新 lint 被触及文档,`新发现 = 后 − 前`。§11、概览这些**没被触及、仍在基线 → 不算新发现 → 不阻塞**。
- 反例:若 update\_section 写入"`dws_vessel_job` **可能**由 xxx 生成",新增一条 `SPEC_NO_SPECULATION`(基线无)→ 整事务退出码 3 拒绝、零写入,`message_zh` 提示"§7 引入臆测词"。

### 6.6 lint 规则要点(完整表由 `rule-catalog` 输出,每条引用契约条款)

结构类(§1–§10 在位有序、§11+ 禁令\[HARD]、§6 双子节、§7 六表、空节"无");锚点类(`Class#method (path)` 格式、禁行号、§4 必带锚、路径存在/符号可 grep\[需 `--source-root`,缺则跳过+WARN]);链接类(目标文件存在、跨文档必带锚、slug 可解析、§5 上游带锚链接);数据名类(§6.x.2/§7 数据名源码可 grep\[用户口述豁免]、§6↔§7 反查一致、§7 孤立资产须有 §10);臆测词类(§1–§9 无"可能/似乎/推测/估计/应该是"、§10 条目格式);归属类(他子系统标识符出现在正文 → WARN,语义裁决留给 LLM);派生文件链接禁令;根文档具名区域 + mermaid fence 浅层校验(**不实现 mermaid parser**);common 轻契约。`STRUCT_TITLE_CANONICAL`(概览≠概述)为 INFO、永不阻塞。

**规则对象字段(每条 lint 规则都是这个结构,`rule-catalog`** **全量输出)**:`{ rule_id, 契约条款, severity: ERROR|WARN|INFO, blocking: HARD|delta|never, scope: [DocKind...] }`。代表性几条:

| rule\_id                   | 契约条款                                | severity | blocking                           | scope                     |
| -------------------------- | ----------------------------------- | -------- | ---------------------------------- | ------------------------- |
| `STRUCT_NO_SECTION_11PLUS` | wiki-principles §1 / refine"禁 §11+" | ERROR    | **HARD**                           | SUBSYSTEM, SINGLE         |
| `ANCHOR_NO_LINENO`         | wiki-principles §2                  | ERROR    | delta                              | 全部                        |
| `DATA_NAME_GREP`           | code-wiki-conventions §8            | ERROR    | delta(需 `--source-root`,缺则跳过+WARN) | SUBSYSTEM, SINGLE         |
| `SPEC_NO_SPECULATION`      | wiki-principles §5                  | ERROR    | delta                              | SUBSYSTEM, SINGLE, COMMON |
| `STRUCT_TITLE_CANONICAL`   | subsystem-prompt 章节名                | INFO     | never                              | SUBSYSTEM, SINGLE         |

- `blocking` 三档:`HARD`=无视基线恒拒绝(如引入 §11);`delta`=仅当"新引入"才拒绝(存量同类问题不阻塞);`never`=只报不拦(如概览≠概述)。
- 正反例(`SPEC_NO_SPECULATION`):正——§7 写"`t_xxx` 由作业同步写入";反——§6 写"可能由 port-gateway 推送"(§1–§9 出现"可能"→ 命中,应把不确定挪进 §10)。

### 6.7 update\_root 六种 kind

`update_root` 只动根文档具名区域、其余字节原样。六种 kind 各带 `action: add|edit|remove` 与对应 payload:

**例**——给 fabusurfer 根新增一个子系统行(`subsystem_row`,引擎按模板固定列序拼行、校验"详细文档"链接可解析):

```json
{ "op": "update_root", "target": "architecture.md", "kind": "subsystem_row",
  "action": "add", "name": "port-foo",
  "row": { "类型": "Java 服务", "端口": "17099", "路径": "port-foo",
           "上游依赖": "port-service", "详细文档": "[查看](./port-foo/architecture.md#1-概览)" } }
```

**例**——加一条依赖边(`mermaid_edge`,要求两端节点已在图中声明,否则 `E_ROOT_EDGE_DANGLING`):

```json
{ "op": "update_root", "target": "architecture.md", "kind": "mermaid_edge",
  "action": "add", "from": "port-data", "to": "port-device" }
```

其余四种:`mermaid_node`(声明节点 `{node_id, label}`)、`protocol_row`(跨系统通信方式表行)、`aux_resource`(辅助资源 bullet)、`common_index_entry`(`## 仓内公共文档` 缺失时容忍创建该节再插入行)。

> **6 种 kind 对应 5 个具名区域**:子系统清单(`subsystem_row`)/ 依赖关系图(`mermaid_node` + `mermaid_edge` 两 kind)/ 跨系统通信方式(`protocol_row`)/ 辅助资源(`aux_resource`)/ 仓内公共文档(`common_index_entry`)。这 5 区即 §3 约束3"4+1 个具名区域";其余根文档内容(拓扑层级、数据资产索引指引、文档维护说明、frontmatter、体系外漂移)`update_root` 一概不碰。

### 6.8 退出码

0 成功 / 2 用法错误 / 3 事务被否决(lint 增量或硬规则)/ 4 寻址失败 / 5 耦合缺失 / 6 替换串过期 / 7 解析失败 / 8 IO / 9 源码根缺失(仅 `--require-source` 时)。`lint` 有发现仍退出 0(发现即产品),`--strict` 时有 ERROR 则退 3。区分"引擎说不"(3/5)与"调用方搭错"(2/4/6),技能侧据此决定让 LLM 改 payload 还是改调用。

### 6.9 测试(unittest;fixtures 从 D:\wiki 真实样本裁剪)

fixtures:drift\_subsystem(概览标题+§11+派生文件链接,仿 port-data)、clean\_subsystem(仿 port-device)、single\_mode(仿 charge-manage-platform)、root\_doc(YAML frontmatter+体系外章节,仿 fabusurfer 根)、ancillary(含合法 `## 11. 附录`,不得误报)、common 两级、中文文件名/内容。
测试组:slug 黄金表(含实测 wild 锚点)、doc\_kind、**解析往返字节一致(第一道门禁)**、问题 ID 稳定性、每条 lint 规则正反例、每个 op 黄金前后对照、耦合/拒绝路径、lint 增量(改漂移文档不引新违规→成功;引新违规→拒绝)、多文档事务回滚零部分写入、refs、UTF-8/中文路径。

**B 门禁**:全部测试绿;往返字节一致在所有 fixtures 成立;`rule-catalog` 每条规则含契约条款引用。

## 7. 阶段 C — wiki-refine 重写(头号痛点)

### 7.1 `wiki-refine/SKILL.md` 改动

- **1.0.b 安装根解析**(新):按 §5 探测顺序(仓内 `<repo-root>\document-systems` → `~/.claude/skills/document-systems` → 配置覆盖)解析得到 `<安装根>`,`<ENGINE_CLI>` 与各契约文件路径均由它展开;三者皆无 → 中文中止。**实现不得回退为 `C:\Users\admin\...` 字面量**(MAINTAINER §13 机械校验);
- **1.2.b 引擎可用性探测**(新):`python <安装根>\scripts\wiki_engine\cli.py rule-catalog`(解释器解析遵循 windows-cn-shell-safety:`python` → `py -3`),失败则中文报错中止;契约缺失中止集扩展至 `common-conventions.md`、`scenario-playbook.md`;
- **1.3** 读根文档 `仓内公共文档` 索引(若有)+ 全局 `D:\wiki\_common\` 清单,纳入可选 target;
- **2.2** 候选集 = 子系统 ∪ 仓库级 common ∪ 全局 common;
- **2.3** 派发占位符新增:`<ENGINE_CLI>`(安装根绝对路径)、`<PLAYBOOK_PATH>`、`<COMMON_CONTEXT>`、`<EXPANDED_SCOPE>`(escalation 批准重派时携带);
- **2.4** A/R/E git-diff 门禁不变(subagent 内部已 dry-run→apply,diff 即引擎验证过的改动;R 仍 git restore);
- **2.4.b escalation 门禁**(新):subagent 返回 `escalation_request` 时,主 agent 打印对象/理由/预期收益,A 允许 → 带 `<EXPANDED_SCOPE>` 重派同话题;R 拒绝 → 已完成部分保留,缺口落 §10。打印样张:
  ```
  本轮 subagent 需读取超出边界的区域才能继续:
    区域:port-service 源码(共享库)
    理由:追踪 OTA 命令发布方,需读 OTAVehicleServiceImpl#sendOtaCommand
    预期收益:闭合 §6.6 数据交互的生产方链路
  请输入:
    A  允许并重新追踪(扩大读取范围)
    R  拒绝(已完成部分保留,缺口落 §10)
  ```
- **2.5** `root_suggestions` → `root_updates`(现成 update\_root payload);A = 主 agent 经引擎 `apply` 应用(不再手工 Edit);S/R 语义不变;
- **2.5.b 公共化门禁**(新,A/S/R):A = 引擎原子应用 promote 事务;S = 相关子系统 §10 记"建议公共化";R = 放弃。打印样张:
  ```
  公共化建议 <i>/<N>:
    事实:ego_info 由外部 AntennaServer.PushEgoInfo 上报落 Mongo,本仓多模块只读副本
    级别:repo   类型:shared-lib
    目标公共文档:_common/ego-info-source.md(仓库级,新建)
    受影响子系统文档:port-data、port-ingest(内联内容将改为引用)
    证据:<grep / 源码锚点>
  请输入:
    A  应用(引擎建/改公共文档并将各处改为引用)
    S  暂不公共化,仅在相关子系统 §10 记一条"建议公共化"
    R  拒绝
  ```
- **`--lint`** **入口**(新):非对话模式,跑 `lint --path <DOC_ROOT> --recursive`,中文汇总后退出;
- **Single mode overrides 同步**:引擎检查两模式都做;common 目标单模式下仅全局级;2.5 仍跳过但 promote(global) 可达并走 2.5.b;`--lint` 作用于单文档(`lint --path <DOC_ROOT>\architecture.md`,不 `--recursive`)。多流程内不得出现内联单模式分支(MAINTAINER §9 Shape-1)。

### 7.2 重写 `wiki-refine/references/refine-subagent-prompt.md`

四轮改为:

- **R1 Trace**:按 DocKind 边界追踪(strict 目标只读本子系统源;light 目标可跨子系统、止步 jar/SDK);命中禁区且确有必要 → 记入 `escalation_request`,先完成不依赖禁区的部分;
- **R2 Classify**:读 playbook,把话题+追踪结果+`<USER_SUPPLEMENT>` 映射到 S1–S8(可多场景),回答分类问题(owner/级别/全解 vs 部分解);
- **R3 Author + Build txn**:撰写中文内容(payload 文件),组装**单个**事务 JSON;根文档影响只产出 `update_root` payload,不入事务;
- **R4 Dry-run → Apply**:`apply --dry-run`;有新违规/耦合缺失 → 修内容或事务再试(**禁止绕过引擎手工 Edit**);干净后真实 `apply`。

自检清单收缩为**语义项**:内容是否真正回答话题 / 口述与代码可验内容分离且各自标注 / owner-级别判断有源码依据 / 跨系统自然语言概述指向正确章节 / 残余不确定性已成可执行 §10 条目。删除臆测词扫描、锚点格式、§6↔§7 一致、数据名 grep 等机械项(引擎已覆盖)。

返回 JSON:`{status, modified, new, root_updates, promotions, escalation_request, txn_summary, summary}`(`status` ∈ `ok|error|blocked_on_escalation`)。单模式 delta 块同步更新。

正常完成示例(S1 全解):

```json
{ "status": "ok",
  "modified": ["port-data/architecture.md"],
  "new": [],
  "root_updates": [],
  "promotions": [],
  "escalation_request": null,
  "txn_summary": "S1 全解 1 条 §10(q_a1b2c3d4),§7.1 追加 dws_vessel_job 行",
  "summary": "确认工班宽表写入方为 port-ingest 同步任务,闭合该疑问" }
```

命中禁区、需升级示例(R1 触发,先交不依赖禁区的部分):

```json
{ "status": "blocked_on_escalation",
  "escalation_request": { "zones": [
    { "kind": "other_subsystem", "target": "port-service",
      "reason": "OTA 发布方在共享库 OTAVehicleServiceImpl,需读其源码闭合 §6.6 生产方" } ] },
  "modified": ["port-vehicle/architecture.md"],
  "summary": "已完成不依赖禁区部分,等待用户授权扩大读取范围" }
```

**C 门禁**:在 fabusurfer 上跑一轮真实话题会话,产出引擎验证过的 diff;构造"引入 §11"与"删 §10 不补正文"的事务,确认被退出码 3/5 拒绝;MAINTAINER §9 内联分支检查通过。

## 8. 阶段 D — promote\_to\_common + 两级 common 落地

- 引擎补齐并联调:`promote_to_common`(按 level 解析目标目录、按 type 从 `references/templates/common-*.md` scaffold、逐 source 字节匹配替换为锚点引用、对新 common 文档+全部 source 跑 lint 增量、全原子)、`init-common`(全局层建极简 `D:\wiki\_common\index.md`,引擎维护)、`refs`、`update_root(common_index_entry)`;
- wiki-refine 2.5.b 公共化门禁启用(C 阶段先以"S 路径降级:§10 记建议公共化"过渡);
- 新建 `document-systems/MIGRATION.md`(**仅文档,执行属 F**):
  - M1 解散 `fabusurfer/global/` → `fabusurfer/_common/coordinate-heading-terms.md`(glossary/repo);
  - M2 修 port-data §11(五条架构调整点→§6/§7 正文,PD-LIN-001..009→§10,移除 §11,解散 lineage-open-questions.md;business-report-lineage-analysis.md 保留并补轻契约 frontmatter);
  - M3 allowlist 生效确认(issue/、whole\_architecture.md、spec/ 不再被误报);
  - M4 存量辅助文档补轻契约;
  - M5 视真实跨仓事实决定首批全局 common(无则全局层合法地近空);
  - 每步标注 \[engine]/\[refine]/\[manual]。

**D 门禁**:fixtures 上端到端跑通 promote(repo+global 各一例);对真实 M1 候选跑 `apply --dry-run` 预演(零写入)确认事务形态正确。

## 9. 关键设计不变量(实现全程不可违背)

1. 引擎**不产生任何派生/状态文件**进 wiki(wiki-principles §7):报告走 stdout,反查 refs 实时计算;唯一例外是作为"全局层根文档"的 `_common/index.md`;
2. 引擎**永不改写标题**、永不整文档重排,只做 span 级替换;
3. 中文内容**一律文件传递**,引擎以 `-X utf8` 调用,所有读写强制 UTF-8(windows-cn-shell-safety);
4. 契约文件是单一事实源:lint 规则引用条款;模板只存 `references/templates/`;
5. escalation 只扩大"读",ownership("写")规则不变;
6. agent-facing prose 英文、用户可见文案中文(引擎 JSON:英文 code + `message_zh`);
7. 单/多模式差异只存在于各 SKILL.md 的一个 overrides 块(MAINTAINER §9)。

## 10. 验证(端到端)

1. `python -X utf8 -m unittest discover document-systems/scripts/wiki_engine/tests`(B/D 各阶段全绿);
2. 往返字节一致:对 D:\wiki 全部真实 md 跑 `parse→render` 比对(只读),零差异;
3. `lint --path D:\wiki\fabusurfer --recursive`:能报出已知存量问题(port-data §11、派生文件链接、概览 INFO),且 ancillary 的合法 `## 11. 附录` 不误报;
4. 真实会话冒烟:技能已 junction 链接到 `C:\Users\admin\.claude\skills\`(仓库即安装目录,`scripts/wiki_engine/` 等新增文件自动可见、无需同步),在 fabusurfer 源仓跑 `/wiki-refine`,完成一个 S1(真实 §10 闭环)与一个 S6 话题,`git -C D:\wiki diff` 审阅;再跑 `/wiki-refine --lint`;
5. 拒绝路径冒烟:手工构造违规事务(引入 §11 / 无耦合删 §10 / 断链引用)逐一确认退出码与 `message_zh`。

## 11. 范围外(后续会话)

- **E — document-systems 接入**:review-prompt 8 检查重新分工(1/2/4/7 全归引擎;3/5/6/8 引擎预标 + LLM 裁决语义残余)、subsystem-prompt Round 3 改"先 `lint --doc` 修干净再语义自检"、document-systems SKILL.md Phase 5 lint-first 与 Phase 1.0 init-common 接线;
- **F — 存量治理执行**:按 MIGRATION.md 对 D:\wiki 执行 M1–M5(每步需用户确认)。

## 12. 文件清单

**新建**:

- `document-systems/references/common-conventions.md`
- `document-systems/references/scenario-playbook.md`
- `document-systems/references/templates/common-{glossary,shared-lib,protocol,infra}.md`
- `document-systems/scripts/wiki_engine/**`(含 tests)
- `document-systems/MIGRATION.md`

**修改**:

- `wiki-refine/SKILL.md`(重写主要流程)
- `wiki-refine/references/refine-subagent-prompt.md`(重写)
- `document-systems/references/templates/root-architecture.md`(+`## 仓内公共文档`)
- `document-systems/references/wiki-principles.md`(§3 一句)
- `document-systems/references/code-wiki-conventions.md`(一行指针)
- `document-systems/MAINTAINER.md`(检查 10–15)

**本次不动**:`document-systems/SKILL.md`、`references/review-prompt.md`、`references/subsystem-prompt.md`、`references/discovery-prompt.md`

**git**:`master` 上拉特性分支 `wiki-engine`,每阶段(A/B/C/D)各自提交,门禁通过后合并。

## 13. 决策确认记录(原开放点,均已定)

| # | 议题 | 结论 |
| - | --- | --- |
| 1 | 首批**全局** common | **已定**:暂无确认的跨仓事实 → **先一律仓库级**(`level=repo`)。全局 `_common/` 结构保留但合法地近空(仅 `index.md`);引擎仍实现 `--level global` 能力,待真出现第二仓消费再 promote 上移。M5 因此默认不产出全局文档 |
| 2 | 技能同步安装方式 | **已定**(实测):`C:\Users\admin\.claude\skills\{document-systems,wiki-refine,...}` 已是 **Junction**,直指 `D:\jk_file\skills\<skill>`。仓库即安装目录——`scripts/wiki_engine/`、新增 `references/*.md` 经 junction **自动可见、无需同步**;引擎按安装根绝对路径(MAINTAINER §13)调用即解析到仓库文件,测试也跑同一份 |
| 3 | `issue/` 区域处理 | **已定**:暂保留、维持 ignored;后续由用户把内容迁入 `spec/`(归 spec-driven-implementation 管辖),本次不展开。`issue/**` 与 `spec/**` 均已在 ignore-globs,引擎无需改动 |
| 4 | 全局 `_common/index.md` | **已定**:保留引擎维护的**极简** `index.md`(按 4 类分组,每条仅 文件/级别/一句话/`owns`),只做"发现/导航";跨文档查询(`questions`/`refs`/grep)走引擎实时计算、不写进 index。common 文档保留 3 节薄骨架(组织模型见 §5 A1) |
| 5 | escalation 文案/粒度 | **已定**:`<EXPANDED_SCOPE>` 按 **zone 粒度**——`kind ∈ other_subsystem \| jar_sdk \| other_repo` + 具体 `target`(子系统名 / jar 名 / 仓名);门禁打印文案见 §7.1 的 2.4.b 样张,实现照此即可 |
| 6 | C 阶段期间 S4 的过渡降级 | **已定**:可接受。C 阶段 S4 暂走"S 路径降级"——在相关子系统 §10 记一条"建议公共化"待确认条目;D 阶段 `promote_to_common` 上线后再把这些条目真正公共化 |

