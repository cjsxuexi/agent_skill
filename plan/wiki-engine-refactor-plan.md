# wiki-refine 工程化改造方案(wiki-engine)

> 状态:**草案 v1,待确认**(2026-06-04)
> 范围:本次实施 A→D 四阶段;E(document-systems 接入)与 F(存量治理执行)留后续会话
> 配套讨论记录:本文档由 brainstorming + 双 Plan agent 设计稿收敛而来,所有"实测"均来自 D:\wiki 与 D:\jk_file\skills 真实文件

---

## 1. 背景与问题

`/wiki-refine` 目前用一个 prose prompt 让 refine subagent 同时做四件事:源码追踪、gap 分析、**机械化改文档**、prose 自检。机械步骤靠 LLM 自觉执行,导致不稳定。实际后果已在 D:\wiki 现身(实测):

- `fabusurfer/port-data/architecture.md`、`port-ingest/architecture.md` 长出违反契约的 `## 11.` 章节;
- `port-data/lineage-open-questions.md` 是违反 wiki-principles §7 的派生问题文件;
- §10 闭环时"该删的不删、该并入正文的没并入"(问题 A-1);
- 跨模块同一事实在多处详写,无 owner、无引用收敛(问题 A-2);
- "所有系统共享内容"无契约、无维护流程:`D:\wiki\common\` 已建但空,`fabusurfer/global/coordinate-heading-terms.md` 是自发雏形(问题 B)。

**改造方向**:把可确定化的部分(解析、校验、结构变更)做成确定性 Python 引擎,由 code agent(claude code / codex)驱动;LLM 只保留语义判断(场景分类、全解/部分解、owner/级别归属、中文撰写)。修改场景枚举为 S1–S8,每类映射固定的引擎事务形态,违规操作被引擎**硬拒绝**。

## 2. 已锁定决策(用户已确认)

| # | 决策 | 内容 |
|---|---|---|
| 1 | 两级 common | 全局 `D:\wiki\common\`(跨仓库)+ 仓库级 `<DOC_ROOT>\common\`(仓内子系统共享)。D:\wiki 是单一 git 仓,两级都在工作树内,相对链接可达:子系统文档→仓库级 `../common/x.md`、→全局 `../../common/x.md` |
| 2 | 工程化边界 | 引擎 = 解析 + 不变量校验(lint)+ 原子结构算子,违规硬拒绝;agent = 场景分类 + 内容撰写 |
| 3 | 组织 | 一个共享引擎(`document-systems/scripts/wiki_engine/`),技能变薄(场景 playbook + 对话编排),**不**新建 common skill |
| 4 | common 类型 | 锁定 4 类:glossary(术语表)/ shared-lib(共享库契约)/ protocol(公共协议)/ infra(基础设施约定),不设"其他" |
| 5 | 读源边界 | 轻量文档(common + 辅助文档)可跨子系统读本仓源码、止步 jar/SDK;严格文档(子系统 architecture.md)仍只读本子系统。**升级机制**:subagent 判断需读禁区 → 返回 escalation 请求 → 主 agent 询问用户 → 同意后扩大范围重派。升级只扩大"读",不改变"写"的归属规则 |
| 6 | 本次范围 | A→D;E、F 后续会话 |

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

**文档三分类(DocKind)**:

| 类别 | 范围 | 规则集 |
|---|---|---|
| strict | 子系统/单系统 `architecture.md`、根文档 | 完整契约(§1–§10 / 根文档四区域) |
| light | common 文档 + `<子系统>/<topic>.md` 辅助文档 | frontmatter + 统一 `## 待确认 / 疑问` 章节 + 锚点格式 + 无臆测词 + 标识符原样;**不**施加 §1–§10 |
| ignored | `issue/**`、`whole_architecture.md`、`spec/**`、`**/.review.md` | allowlist 写死在 common-conventions.md 的 fenced block,引擎读取;不校验 |

**关键现实约束(实测,实现全程不可违背)**:

1. §1 标题一半文档是"概览"非"概述" → 契约按**位置+编号**而非字面标题;锚点必须从实际标题用 GitHub-exact slugger 计算(实测样例:`### 6.6 OTA / 版本 / 文件日志流` → `#66-ota--版本--文件日志流`,CJK 保留、`/ ` 产生双连字符);引擎**永不改写标题**。
2. 渲染必须是**外科手术式字节拼接**(按解析时记录的 offset 做 span 级替换),禁止整文档重排;`render(parse(x)) == x` 字节级成立是 B 阶段第一道门禁。否则 git diff 噪声爆炸、lint 增量失真。
3. 根文档存在 YAML frontmatter、体系外 `## 系统架构特点`、非法 `## 6.` 等漂移 → 解析容忍、lint 报告、`update_root` 只动具名区域,其余字节原样。
4. `alarm-architecture.md` 含合法 `## 11. 附录` → §11+ 禁令只适用于 strict 文档,light 文档不受限(DocKind 决定规则集)。

## 4. 修改场景枚举 S1–S8(方案核心,对应问题 A/B)

| ID | 触发信号 | agent 的分类判断 | 引擎事务形态 | 用户门禁 |
|---|---|---|---|---|
| **S1** §10 全解 | 既有 §10 条目被追踪结果/用户补充完全回答,无残余未知 | "条目的**每一个**子句都闭环了吗?"有残余 → S2 | `resolve_question(full)` + 同事务耦合 `update_section`(把结论写进正文对应章节)。**引擎强制耦合**:删 §10 条目而不补正文 → 硬拒绝(也可提供 existing-anchor 证明结论已在正文) | 现有 A/R/E |
| **S2** §10 部分解 | 部分子句闭环,部分仍未知 | "哪些闭环、哪些保留?残余如何重新表述?" | `resolve_question(partial, 残余重写文本)` + 已确认部分 `update_section` | A/R/E |
| **S3** 同一事实多文档详写 | 追踪发现同一内部事实在 ≥2 个文档详细出现 | "owner 是谁?"指南:定义该事实的 `Class#method` 所在子系统 = owner | `move_with_reference`:owner 保留详写,其余替换为锚点引用 + 一句概述 | A/R/E |
| **S4** 跨系统共享事实 | ≥2 子系统需要、无单一属主(术语/共享库/协议/基础设施) | 放置阶梯(见 §5 A1)定级别+类型 | `promote_to_common(level, type)` + 各处 `move_with_reference` 改引用,scaffold 目标 common 文档(如不存在),**全原子** | **新增公共化门禁 A/S/R**(S=暂不公共化,相关子系统 §10 记"建议公共化") |
| **S5** 新增已验证事实 | 追踪发现未记录的、可代码验证的事实 | "归哪个章节?数据名可 grep 吗?" | `update_section`(引擎 lint 管住六渠道、§6↔§7 一致) | A/R/E |
| **S6** 新增不确定点 | 链路未闭环/生产方未知/边界模糊 | 按 `[§<位置>] …。已检查:…。建议核实方向:…` 表述 | `add_question`(引擎校验 §10 格式) | A/R/E |
| **S7** 用户口述知识 | `<USER_SUPPLEMENT>` 含 jar/SDK 内部、运行时配置、业务规则 | "归哪个章节?与代码可验内容分段" | `update_section` 带 `> 来源:用户口述(日期)`(数据名豁免 grep 但必须带标注) | A/R/E |
| **S8** 根文档影响 | 子系统清单缺行/依赖边错漏/协议缺行/辅助资源漂移/公共索引缺行 | "哪个根工件?构造精确的行/边" | subagent 返回现成 `update_root` payload;主 agent 经用户确认后**用引擎应用**(替代现行手工 Edit) | 现有根门禁 A/S/R,改为引擎执行 |

**横切规则**:
- 一个话题可命中多场景 → 合成**一个事务**,先 `--dry-run` 自修复到干净,再真实 apply(原子:全成或全不成);
- owner / 级别 / 全解 vs 部分解是 **agent 的语义判断**,引擎只校验结构化结果;
- **escalation**:R1 追踪命中禁区(他子系统源码 / jar / SDK / 他仓)且确有必要 → 先完成不依赖禁区的部分,返回 `escalation_request{zones, reason}` → 主 agent 询问用户 → 同意则带 `<EXPANDED_SCOPE>` 重派,拒绝则缺口落 §10。经授权读 jar/SDK 得来的内容标注 `> 来源:经用户授权阅读 <对象>(YYYY-MM-DD)`,优先落 shared-lib 类 common 文档。

## 5. 阶段 A — 契约文件 + 场景 playbook

全部在 `D:\jk_file\skills\document-systems\` 下(wiki-refine 运行时按安装根 `C:\Users\admin\.claude\skills\document-systems\...` 绝对路径引用,MAINTAINER §3 模式)。

**A1 新建 `references/common-conventions.md`**(agent-facing 英文):
- 两级语义 + 引用路径规则(决策 1);
- **放置判定阶梯**:① 事实归单一子系统所有 → 留在该子系统文档,他处引用;② 本仓 ≥2 子系统共享且无单一属主 → 仓库级 common;③ 确有第二个仓库消费或全公司标准 → 全局 common。宁低勿高;拿不准 → 仓库级 + 记"建议全局化"待确认条目;
- 4 类 common 文档轻量结构(各含统一尾章 `## 待确认 / 疑问`,条目格式同 wiki-principles §5 → 引擎 `questions` 可全 wiki 枚举);frontmatter:`common_type` / `level: repo|global` / `owns: <事实稳定id>`;文件名 kebab-case 英文;
- Ownership 扩展:common 文档拥有共享事实,子系统文档必须锚点引用、不得复制内部细节;
- **读源边界阶梯 + escalation 条款**(决策 5 全文);
- **ignore-globs fenced block**(引擎读取):`issue/**`、`whole_architecture.md`、`spec/**`、`**/.review.md`。

**A2 新建 `references/scenario-playbook.md`**(agent-facing 英文):§4 的 S1–S8 表 + 三个判断指南(owner 归属 / common 级别阶梯 / 全解 vs 部分解)+ 横切规则 + escalation 流程。

**A3 新建 4 个模板** `references/templates/common-{glossary,shared-lib,protocol,infra}.md`:frontmatter + `## 1. 范围与级别` + 类型主体(glossary:术语表格;shared-lib:对外契约/调用面 + 使用方,禁库内部细节;protocol:协议定义 + 生产方/消费方;infra:约定 + 适用范围)+ `## 待确认 / 疑问`。**引擎 scaffold 从这些文件读取,引擎包内不复制模板(单一来源)**。

**A4 修改 `references/templates/root-architecture.md`**:在 `## 数据资产索引指引` 与 `## 辅助资源` 之间新增固定章节 `## 仓内公共文档`(含 `<REPO_COMMON_INDEX_ROWS>` 占位 + 指向 `./common/` 与全局 `../common/` 的固定文案)。

**A5 微调共享契约**(遵守 MAINTAINER §1 规则不丢 / §2 领域中立):`wiki-principles.md` §3 加一句领域中立的"共享事实由指定 owner 文档拥有,他处引用不复制";`code-wiki-conventions.md` 加一行指针(common 文档 attribution 遵循其 §3)。

**A6 修改 `MAINTAINER.md`**,新增检查 10–15:
- 10 引擎↔契约对齐:每条 lint 规则引用契约条款;每条机械契约条款有引擎检查或显式 LLM-only 标记;
- 11 章节名常量对齐:引擎常量 = 模板/契约字面;§4 对齐集合扩展至 common 模板 + common-conventions;
- 12 引擎输出语言:英文 `rule_id`/`code` + `message_zh`;技能只对用户展示 `message_zh`;
- 13 wiki-refine 按安装根绝对路径调用引擎与新契约文件,缺失则中文报错中止;
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

| 命令 | 用途 |
|---|---|
| `outline --path <md>` | 解析结构树(章节/§6 入口/§7 表/offset),供 agent 寻址 |
| `questions --path <md\|dir> [--recursive]` | 枚举 §10/待确认 条目(含稳定 ID),覆盖 strict + light 文档 |
| `lint --path <md\|dir> [--recursive --source-root <源仓根> --strict --rules <id,..>]` | 全量不变量校验,JSON 发现清单 |
| `apply --txn <json 文件> [--dry-run --source-root]` | 原子多算子事务 |
| `init-common --level repo\|global --name <slug> --type <4类>` | 从模板 scaffold common 文档;全局层维护极简 `common/index.md` |
| `refs --path <md> [--anchor --scope doc-root\|wiki]` | 实时反查:谁链接到该文档/锚点 |
| `rule-catalog` | 输出完整 lint 规则表(id→契约条款→severity→blocking→范围) |

### 6.3 稳定问题 ID

`q_` + sha1(`doc相对路径 ‖ [§位置]规范化 ‖ 疑问首句规范化`)[:8]。性质:改"已检查/建议核实方向"不变 ID(S2 常见操作);改 `[§位置]` 才换 ID(问题真的移动了,语义正确);同文本不同文档 → 不同 ID。

### 6.4 章节寻址

`{section:"6", entry:"6.2"|"标识符子串", subsection:"数据交互"|"处理流程"|"7.3", anchor_mode: replace|append|append_table_row}`。0 命中 → `E_ADDR_NOTFOUND`;多命中 → `E_ADDR_AMBIGUOUS`(要求改用编号形式)。`append_table_row` 校验列数与表头一致。`move/promote` 的替换额外要求 `replace_match_file` 与现文**字节匹配**(防陈旧编辑,`E_MATCH_STALE`)。纯结构寻址,永不用行号。

### 6.5 事务语义(核心)

1. 加载所有 target 文档,逐文档记录 lint **基线**;
2. 各 op 静态校验(schema、寻址可解析、字节匹配、耦合存在);
3. 按序内存应用(span 替换,op 间重算 offset);
4. **硬规则**(无视基线,恒拒绝):向 strict 文档引入 §11+;`resolve_question(full)` 无耦合 body 编辑或有效 existing-anchor 证明;新增指向派生文件的链接;
5. **lint 增量**:`新发现 = 后 − 前`,键为 `(rule_id, 结构位置, 消息hash)`(非行号);blocking 新发现 → 整体拒绝;**存量漂移不阻塞**(概览标题、未触及的旧 §11);
6. 提交:同目录临时文件 + rename,全写或全不写。`--dry-run` 走完 1–5,输出 diff 预览 + 发现,零写入。

### 6.6 lint 规则要点(完整表由 `rule-catalog` 输出,每条引用契约条款)

结构类(§1–§10 在位有序、§11+ 禁令[HARD]、§6 双子节、§7 六表、空节"无");锚点类(`Class#method (path)` 格式、禁行号、§4 必带锚、路径存在/符号可 grep[需 `--source-root`,缺则跳过+WARN]);链接类(目标文件存在、跨文档必带锚、slug 可解析、§5 上游带锚链接);数据名类(§6.x.2/§7 数据名源码可 grep[用户口述豁免]、§6↔§7 反查一致、§7 孤立资产须有 §10);臆测词类(§1–§9 无"可能/似乎/推测/估计/应该是"、§10 条目格式);归属类(他子系统标识符出现在正文 → WARN,语义裁决留给 LLM);派生文件链接禁令;根文档具名区域 + mermaid fence 浅层校验(**不实现 mermaid parser**);common 轻契约。`STRUCT_TITLE_CANONICAL`(概览≠概述)为 INFO、永不阻塞。

### 6.7 update_root 六种 kind

`subsystem_row`(子系统清单表行)/ `mermaid_node` / `mermaid_edge`(增删边,要求两端节点已声明)/ `protocol_row` / `aux_resource` / `common_index_entry`(`## 仓内公共文档` 缺失时容忍地创建该节再插入)。只动具名区域,其余字节原样。

### 6.8 退出码

0 成功 / 2 用法错误 / 3 事务被否决(lint 增量或硬规则)/ 4 寻址失败 / 5 耦合缺失 / 6 替换串过期 / 7 解析失败 / 8 IO / 9 源码根缺失(仅 `--require-source` 时)。`lint` 有发现仍退出 0(发现即产品),`--strict` 时有 ERROR 则退 3。区分"引擎说不"(3/5)与"调用方搭错"(2/4/6),技能侧据此决定让 LLM 改 payload 还是改调用。

### 6.9 测试(unittest;fixtures 从 D:\wiki 真实样本裁剪)

fixtures:drift_subsystem(概览标题+§11+派生文件链接,仿 port-data)、clean_subsystem(仿 port-device)、single_mode(仿 charge-manage-platform)、root_doc(YAML frontmatter+体系外章节,仿 fabusurfer 根)、ancillary(含合法 `## 11. 附录`,不得误报)、common 两级、中文文件名/内容。
测试组:slug 黄金表(含实测 wild 锚点)、doc_kind、**解析往返字节一致(第一道门禁)**、问题 ID 稳定性、每条 lint 规则正反例、每个 op 黄金前后对照、耦合/拒绝路径、lint 增量(改漂移文档不引新违规→成功;引新违规→拒绝)、多文档事务回滚零部分写入、refs、UTF-8/中文路径。

**B 门禁**:全部测试绿;往返字节一致在所有 fixtures 成立;`rule-catalog` 每条规则含契约条款引用。

## 7. 阶段 C — wiki-refine 重写(头号痛点)

### 7.1 `wiki-refine/SKILL.md` 改动

- **1.2.b 引擎可用性探测**(新):`python <安装根>\scripts\wiki_engine\cli.py rule-catalog`(解释器解析遵循 windows-cn-shell-safety:`python` → `py -3`),失败则中文报错中止;契约缺失中止集扩展至 `common-conventions.md`、`scenario-playbook.md`;
- **1.3** 读根文档 `仓内公共文档` 索引(若有)+ 全局 `D:\wiki\common\` 清单,纳入可选 target;
- **2.2** 候选集 = 子系统 ∪ 仓库级 common ∪ 全局 common;
- **2.3** 派发占位符新增:`<ENGINE_CLI>`(安装根绝对路径)、`<PLAYBOOK_PATH>`、`<COMMON_CONTEXT>`、`<EXPANDED_SCOPE>`(escalation 批准重派时携带);
- **2.4** A/R/E git-diff 门禁不变(subagent 内部已 dry-run→apply,diff 即引擎验证过的改动;R 仍 git restore);
- **2.4.b escalation 门禁**(新):subagent 返回 `escalation_request` 时,主 agent 打印对象/理由/预期收益,A 允许 → 带 `<EXPANDED_SCOPE>` 重派同话题;R 拒绝 → 已完成部分保留,缺口落 §10;
- **2.5** `root_suggestions` → `root_updates`(现成 update_root payload);A = 主 agent 经引擎 `apply` 应用(不再手工 Edit);S/R 语义不变;
- **2.5.b 公共化门禁**(新,A/S/R):展示 事实/级别/类型/目标公共文档(新建|追加)/受影响文档清单/证据;A = 引擎原子应用 promote 事务;S = 相关子系统 §10 记"建议公共化";R = 放弃;
- **`--lint` 入口**(新):非对话模式,跑 `lint --scope`,中文汇总后退出;
- **Single mode overrides 同步**:引擎检查两模式都做;common 目标单模式下仅全局级;2.5 仍跳过但 promote(global) 可达并走 2.5.b;`--lint` 作用于单文档。多流程内不得出现内联单模式分支(MAINTAINER §9 Shape-1)。

### 7.2 重写 `wiki-refine/references/refine-subagent-prompt.md`

四轮改为:
- **R1 Trace**:按 DocKind 边界追踪(strict 目标只读本子系统源;light 目标可跨子系统、止步 jar/SDK);命中禁区且确有必要 → 记入 `escalation_request`,先完成不依赖禁区的部分;
- **R2 Classify**:读 playbook,把话题+追踪结果+`<USER_SUPPLEMENT>` 映射到 S1–S8(可多场景),回答分类问题(owner/级别/全解 vs 部分解);
- **R3 Author + Build txn**:撰写中文内容(payload 文件),组装**单个**事务 JSON;根文档影响只产出 `update_root` payload,不入事务;
- **R4 Dry-run → Apply**:`apply --dry-run`;有新违规/耦合缺失 → 修内容或事务再试(**禁止绕过引擎手工 Edit**);干净后真实 `apply`。

自检清单收缩为**语义项**:内容是否真正回答话题 / 口述与代码可验内容分离且各自标注 / owner-级别判断有源码依据 / 跨系统自然语言概述指向正确章节 / 残余不确定性已成可执行 §10 条目。删除臆测词扫描、锚点格式、§6↔§7 一致、数据名 grep 等机械项(引擎已覆盖)。

返回 JSON:`{status, modified, new, root_updates, promotions, escalation_request, txn_summary, summary}`。单模式 delta 块同步更新。

**C 门禁**:在 fabusurfer 上跑一轮真实话题会话,产出引擎验证过的 diff;构造"引入 §11"与"删 §10 不补正文"的事务,确认被退出码 3/5 拒绝;MAINTAINER §9 内联分支检查通过。

## 8. 阶段 D — promote_to_common + 两级 common 落地

- 引擎补齐并联调:`promote_to_common`(按 level 解析目标目录、按 type 从 `references/templates/common-*.md` scaffold、逐 source 字节匹配替换为锚点引用、对新 common 文档+全部 source 跑 lint 增量、全原子)、`init-common`(全局层建极简 `D:\wiki\common\index.md`,引擎维护)、`refs`、`update_root(common_index_entry)`;
- wiki-refine 2.5.b 公共化门禁启用(C 阶段先以"S 路径降级:§10 记建议公共化"过渡);
- 新建 `document-systems/MIGRATION.md`(**仅文档,执行属 F**):
  - M1 解散 `fabusurfer/global/` → `fabusurfer/common/coordinate-heading-terms.md`(glossary/repo);
  - M2 修 port-data §11(五条架构调整点→§6/§7 正文,PD-LIN-001..009→§10,移除 §11,解散 lineage-open-questions.md;business-report-lineage-analysis.md 保留并补轻契约 frontmatter);
  - M3 allowlist 生效确认(issue/、whole_architecture.md、spec/ 不再被误报);
  - M4 存量辅助文档补轻契约;
  - M5 视真实跨仓事实决定首批全局 common(无则全局层合法地近空);
  - 每步标注 [engine]/[refine]/[manual]。

**D 门禁**:fixtures 上端到端跑通 promote(repo+global 各一例);对真实 M1 候选跑 `apply --dry-run` 预演(零写入)确认事务形态正确。

## 9. 关键设计不变量(实现全程不可违背)

1. 引擎**不产生任何派生/状态文件**进 wiki(wiki-principles §7):报告走 stdout,反查 refs 实时计算;唯一例外是作为"全局层根文档"的 `common/index.md`;
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
4. 真实会话冒烟:同步技能到 `C:\Users\admin\.claude\skills\`(沿用现有安装方式,执行时确认),在 fabusurfer 源仓跑 `/wiki-refine`,完成一个 S1(真实 §10 闭环)与一个 S6 话题,`git -C D:\wiki diff` 审阅;再跑 `/wiki-refine --lint`;
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

## 13. 开放点(待你确认/可优化)

| # | 开放点 | 当前默认 |
|---|---|---|
| 1 | 首批**全局** common 是否已有真实跨仓事实?(如 `grpc-api`/`common-api` jar 是否被 fms-server 等第二个仓库消费) | 未确认前一律仓库级;全局层可以合法地近空 |
| 2 | 技能从 `D:\jk_file\skills` 同步到 `C:\Users\admin\.claude\skills\` 的安装方式(复制/脚本/junction?) | 执行到验证步骤时与你确认 |
| 3 | `issue/` 区域完全 ignored 还是也施加轻契约? | 完全 ignored,后续量大再收编 |
| 4 | 全局 `common/index.md` 由引擎维护(`init-common`/promote 时更新) vs 不要索引文件 | 引擎维护极简索引(视为全局层"根文档",非派生文件) |
| 5 | escalation 门禁的交互文案、`<EXPANDED_SCOPE>` 的粒度(整个子系统 or 指定路径) | 按 zone 粒度(子系统级 / 指定 jar),文案实现时给样张 |
| 6 | C 阶段期间 S4 的过渡降级("§10 记建议公共化")是否可接受 | 可接受,D 阶段启用真实 promote |
