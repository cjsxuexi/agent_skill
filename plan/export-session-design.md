# export-session 会话导出分析技能设计

> 状态:**v5 — 定稿(SUP-4 落地)**。§17 三点已定;平台前提二次实测复核通过;技能骨架(SKILL.md + 固定模板 + 自评记录文件 + .gitignore)已随本 skill 落盘。**确定性 Python 引擎 + launcher 的实现留待 writing-plans/TDD 单独推进(见 §18)。**
> 历史:v1 06-18;v2 06-29;v3 06-29 二轮;v4 06-29 三轮;**v5 07-01 定稿**。
> **最终目标(用户确认)**:借本 skill 实现 **自动化维护高质量 wiki(`D:\wiki\`)+ skill/MCP 问题监控发现**。本技能只做"观测 + 评估 + 建议",**是否改、如何改一律由人拍板**;wiki 的实际维护走 **/wiki-refine**(保持 wiki 结构不乱)。
> 工程路线:**确定性 Python 引擎**(解析/清洗/渲染/编目/索引/打分 + wiki 触点检测,零 LLM)+ **薄编排**(触发见 §6)+ **一次受控分析调用**(筛选判断 + 写分析文档 + 写自评)+ TDD。

---

## 0. 修订记录

**v4 → v5(SUP-4 定稿,本次):**

| 条目 | v4 | v5(定稿) | 依据 |
| -- | -- | -- | -- |
| §17 待确认 3 点 | 🔶 待用户确认 | **全部定案**(见 §17):触发=分层(主:人类评论/@mention;真·全自动:本地 SessionEnd hook;兜底:schedule-poll);D2 无原文时标"低置信疑似";会话定位主用 `issue runs.result.session_id` | 监工-执行闭环自主推进(SUP-25 目标"尽量不需要人介入");沿用 v2–v4 用户已确认的方向 |
| 平台前提 | v4 一次实测 | **二次复核通过**:`autopilot trigger-add` 仅 `schedule|webhook`;`issue runs[].result.session_id` 确认存在(实测值 `637fce62-…`),且 comment-run 携带 `trigger_comment_id`(人类作者锚点)、`runtime_id`/`work_dir`(同机校验) | 本次 CLI 实测 |
| 交付物 | 仅设计文档 | **技能骨架落盘**:`SKILL.md`、`references/analysis-template.md`、`export-session-eval-log.md`(已建,`.gitignore`)——见 §18 | 本 issue 三项要求之"创建评估记录文件"需具体落地 |

**§0 平台能力实测(维持 v4 结论,二次复核):autopilot 不能按"状态变更/操作者=人"准入,裸改状态不触发 run。**
1. CLI:`multica autopilot trigger-add --help` → 描述为 "Add a schedule or webhook trigger";`--kind` 仅 `schedule | webhook`(+ `trigger` 手动);无事件/状态/操作者选项。
2. `multica issue runs <id> --output json`:comment 触发的 run `kind:"comment"` 且带 `trigger_comment_id`+`trigger_summary`;本次 stage 提升触发我的 run 为 `kind:"direct"`;裸改状态(上一轮 `in_review`)未见新 run。→ **能触发并自带人类身份的是评论/@mention,不是裸改状态。**
3. `result.session_id` 字段确认存在(可精确定位被分析会话的 jsonl),`runtime_id`/`work_dir` 可校验同机可达。

---

## 1. 背景与目标

Claude Code 会话以 JSONL 存于 `~/.claude/projects/<编码cwd>/<uuid>.jsonl`(+ 同名子目录子代理/workflow)。三硬伤:多文件、噪音淹没信号(快照/注入/簿记行占大半,最大会话约 80 万~100 万 token)、文件名裸 UUID。**本期仅做 Claude Code;codex 会话格式不同,放 phase 2。**

**目标**:确定性引擎做"解析+清洗+渲染+编目+索引+打分+wiki 触点检测";任务结束后**自动触发**(见 §6),受控分析调用按固定模板产出**双维分析文档**,并维护跨次自评记录。**最终用途**:喂养"自动维护高质量 wiki + skill 问题监控"闭环——本技能负责发现与建议,人拍板,wiki 维护走 /wiki-refine。

## 2. 决策表(v5)

| #  | 决策 | 内容 |
| -- | -- | -- |
| 0  | 用途与消费者 | 导出物供 Claude 分析;固定双分析目标见 #10;最终目标见 §1。 |
| 1  | 存储格式 = 混合 | `transcript.md` + `summary.json` + 可选 `raw/`;每次分析产出 `analysis.md`(§8)。 |
| 2  | 选择方式 = 自动评估筛选 | 引擎按"能否完成 D1/D2"打分自动选;**未选文件 + 当时不选原因在筛选当时落盘**(§7)。 |
| 3  | 内容粒度 | 含 thinking、子代理/workflow;裁 文件快照、system-reminder、超长结果(截断留 raw/)、注入文件(折叠一行)。 |
| 4  | 架构 = 确定性引擎 + 受控分析调用 | JSONL→导出零 LLM;筛选判断与分析正文由一次 headless 调用完成,带护栏(§12/§13)。 |
| 5  | EXPORT_ROOT | 默认 `D:\claude-sessions`,首次询问记住。 |
| 6  | raw/ 默认开 | `--no-raw` 关。 |
| 7  | 脱敏 | 不自动脱敏,仅警示。 |
| 8  | 生命周期极简 | status/tags/notes + 跨会话索引;删除不进 skill。 |
| 9  | **触发 = 任务完成后自动触发(分层,§6)** | 主:人对结束的 issue 发评论/@mention export-session(自带已认证人类发起者);真·全自动:本地 cc 的 `SessionEnd` hook;兜底:scheduled autopilot 轮询。**对每个被这样触发的会话都分析。** |
| 10 | **分析目标 = 固定双维(D2=会话内 wiki 保真度)** | **D1 = 评估 skill/MCP 运行效果**(摩擦点→问题+改造建议);**D2 = 会话内 wiki 使用保真度**:本次 session 用 wiki 内容时有无幻觉/误解,wiki 描述不完整/不准确是否致 code agent 跑偏 → wiki 问题 + 建议(交 /wiki-refine)。 |
| 11 | 自评记录 = AI 自维护 | `D:\jk_file\skills\export-session\export-session-eval-log.md`,**`.gitignore`**;每次分析完比本次 vs 历次(D1/D2)是否改善 + 建议(§9)。 |
| 12 | 只评估用户主动发起的会话 | 触发渠道即人类身份(评论/@mention 自带已认证发起者)+ 自噬排除 + 会话级兜底(§12)。 |
| 13 | **只发现+建议,人拍板** | 本技能不自动改 wiki/skill;**是否改、如何改都由人决定**;wiki 维护走 /wiki-refine。 |

## 3. 总体架构(v5)

```
┌─ 触发层(§6,分层)─────────────────────────────────────────────┐
│ 主:人对"已结束的 issue"发评论/@mention export-session(自带人类身份) │
│    → export-session agent run(kind=comment,携带 trigger_comment_id) │
│ 真·全自动(本地 cc):settings.json 的 SessionEnd hook → launcher     │
│ 兜底:scheduled autopilot 轮询 + agent 内 best-effort 筛新近完成      │
├─ 编排层(SKILL.md + launcher)────────────────────────────────────┤
│ ① 经 `multica issue runs <issue>` 取 result.session_id → 定位会话     │
│    (本地 hook 场景:hook 直接注入 session_id)                        │
│ ② 引擎导出 + score 打分(选/不选+理由草案)+ wiki 触点检测            │
│ ③ 受控分析:确认筛选 + 写 analysis.md(D1+D2)+ 写自评。护栏 §12/§13  │
├─ 引擎层(scripts/session_export/,3.8+ stdlib)──────────────────────┤
│  catalog parse render summarize  score  wiki_touch  index config     │
│  wiki_touch:从会话确定性识别"用到 wiki 的工具调用"并取被引原文        │
└──────────────────────────────────────────────────────────────────┘
```

`wiki_touch`:确定性地从会话标出 **wiki 触点**——读 `D:\wiki\` 下文件的 `Read/Grep/Glob`、抓 wiki 的 `WebFetch`、`mcp__ones_wiki__*` 调用、document-systems/wiki-refine 使用等;并抓取这些触点**实际引用的 wiki 段落**供分析比对。

## 4. 数据流(v5)

```
[任务完成 → 自动触发(§6)] → export-session agent run / 本地 hook
  0. 护栏(§12):确认触发者为人 + 非自噬 + 目标会话有效;不过则记日志退出
  1. 定位会话:multica issue runs <issue> → result.session_id(本次工作的 cc 会话)
               (本地 hook:直接用注入的 session_id;排除 export-session 自己的 run)
  2. config/catalog:EXPORT_ROOT、探测 projects 根、按 session_id 定位 jsonl
  3. export:parse→render(transcript.md)+summarize(summary.json)[+raw/]
  4. score + wiki_touch:打分 {选中,未选+理由}→写 analysis.md §1;标出 wiki 触点
  5. analyze(受控 headless):
       a) 确认/修正筛选(理由继续记 §1)
       b) D1:摩擦点等→评估 skill/MCP 效果→问题+改造建议
       c) D2:对每个 wiki 触点,比对"agent 当时怎么用/怎么理解"vs"被引 wiki 原文"
              → 标 幻觉/误解;并判 wiki 描述不完整/不准确是否致跑偏 → wiki 问题+建议
              (无确切被引原文时标"低置信疑似",不硬判——§17.2)
       d) 收尾回填"未选项事后评估"(§2)
  6. index:重算 INDEX.md / index.json
  7. eval:更新 export-session-eval-log.md(本次 vs 历次,D1/D2)
  8. report:输出 analysis.md 路径(评论场景可回贴摘要,但不 @ 触发者避免循环)
```

## 5. 产物布局(v5)

```
<EXPORT_ROOT>/                              默认 D:\claude-sessions
├─ INDEX.md / index.json / .catalog-cache.json / .config.json
└─ 2026-06-29_<标题>_<id8>/
   ├─ transcript.md  summary.json  subagents/  raw/
   └─ analysis/<时间戳_目标>/analysis.md     # 每次分析一份(D1+D2)

D:\jk_file\skills\export-session\            # 本 skill 自身(随仓库)
├─ SKILL.md                                  # 行为规范/编排
├─ references/analysis-template.md           # 固定分析模板(§8)
├─ scripts/session_export/ + scripts/tests/  # 确定性引擎 + pytest(Stage 1 落地)
├─ export-session-eval-log.md                # AI 自维护跨次自评,.gitignore
└─ .gitignore                                # 忽略 eval-log 与 py/pytest 产物

D:\jk_file\skills\plan\export-session-design.md  # 本设计(Stage 1 从 skill 目录迁至此,与 plan/ 惯例一致)
```

**wiki 问题不在 `D:\wiki` 旁另落清单**(避免结构混乱);D2 发现只进 `analysis.md`,作为 /wiki-refine 的输入由人驱动维护。

## 6. 触发机制(v5:分层,任务完成后自动)

需求是"任务执行完后自动触发"。平台实测(§0)决定了分层方案:

**主机制 · 人对结束的 issue 发评论/@mention export-session**(在 Multica 上是最接近"自动 + 可证人类发起"的可靠信号):
- **为什么满足"只评估用户主动发起"**:评论/@mention 触发的 run 是 `kind:comment`,平台把**已认证的人类发起者**注入运行上下文,并带 `trigger_comment_id`(指向人类作者的评论)。即"触发渠道本身=人类身份证明",无需再去查"谁改了状态"(状态操作者 API 查不到)。
- **怎么定位要分析的会话**:export-session agent 跑 `multica issue runs <issue> --output json`,取该 issue 上**工作 run 的 `result.session_id`**(本次实测该字段确存在,值如 `637fce62-…`),据此精确定位 `~/.claude/projects/.../<session_id>.jsonl`——比"猜最新 mtime"可靠,也天然排除 export-session 自己的 run。
- **用户成本**:≈ 原本"标已完成"一步(改成发一条短评论/@mention)。

**真·全自动机制 · 本地 Claude Code 的 `SessionEnd` hook**(会话一结束就自动跑,零人工动作):
- 在 `settings.json` 配 `SessionEnd` hook → launcher;hook 直接注入 `session_id`,省去 `issue runs` 定位。
- 代价:本地 hook 自身无法区分"人发起 vs agent 发起",需 launcher 套 §12 的"用户发起"过滤(顶层会话、非 export-session cwd、非空实质轮次等)。
- 前提:执行 hook 的 runtime 与产生会话的 runtime 同机/共享 `~/.claude/projects`(§13.6)。**若用户在 Multica 之外本地跑 cc,这是首选。**

**兜底(最弱)· scheduled autopilot 轮询**:一个 cron autopilot 定时跑 export-session agent,扫近段"已完成"的 issue 并分析其 `session_id` 会话。**缺点**:平台无"状态操作者"查询,无法证明"已完成"是人点的,"只评估用户发起"在此模式下只能尽力而为(可加"该 issue 最近有人类评论/由人创建"等弱信号)。

> 默认采用**主机制**;本地纯 cc 场景用 **SessionEnd hook**;两者都不可用时退**轮询**。三者都在 launcher 层收敛到同一后续流程(§4 step 1 之后)。

## 7. 自动评估筛选与未选记录(沿用)

筛选单位含"哪些会话/哪些导出文件";标准=`能否完成 D1/D2`;`score.py` 给确定性草案(信号:目标 skill/MCP 命中、摩擦点数、是否有 wiki 触点、体量/预算)。**筛选当时必记**:① 未选文件 ② 当时不选原因 → `analysis.md` §1。**产出时回填**:当时不选是否合理(§8 §2),误退率反哺 §9 与模板。

## 8. 分析文档固定模板(v5)

模板文件随 skill 落盘于 `references/analysis-template.md`(可用)。骨架:

```markdown
---
schema_version: 1
template_version: 3
analysis_goals: [skill_mcp_effectiveness, wiki_usage_fidelity]
session_id: <uuid>
wiki_root: D:\wiki
generated_at: <ts>
---
# 会话分析报告 — (<日期>)
> ⚠ 可能含密钥/内部 URL,复用/外传前自查。

## 1. 选择决策(筛选阶段实时写)
| 文件/会话 | 选中? | 理由 | 记录时刻 |

## 2. 未选项事后评估(产出时回填)
| 未选文件 | 当时不选理由 | 事后评估 | 若应补选的影响 |

## 3. D1 · skill/MCP 运行效果
- 摩擦点(错误/重试/权限/用户纠正)归因 → 问题清单(可监控) + 改造建议(可执行)

## 4. D2 · 本会话 wiki 使用保真度
对本会话每个 wiki 触点(wiki_touch 标出):
| wiki 触点(文件/页/调用) | agent 当时如何使用/理解 | 比对被引原文 | 判定 | 后果 |
判定 ∈ {正确, 幻觉(编造/记错), 误解(曲解原文), wiki 不完整致跑偏, wiki 不准确致跑偏, 低置信疑似}
- 无确切被引原文(凭记忆用 wiki)→ 标"低置信疑似",不硬判幻觉。
- → wiki 改进建议(具体到页/段),**交 /wiki-refine 维护;是否改、如何改由人定**。

## 5. 结论与建议(D1+D2 汇总,排优先级;全部为建议,人拍板)

## 6. 与历史对比摘要 → 指向 §9 自评本次条目
```

模板稳定、内容随过程累积(§1 筛选时、§3/§4 分析时、§2 收尾时);`template_version` 可跨次演进(动因来自 §9)。这正是需求所说"固定模板并在整个分析过程中不断调整"。

## 9. 自评记录文件(v5)

`D:\jk_file\skills\export-session\export-session-eval-log.md`(`.gitignore`,**本 issue 已创建并初始化**)。每次分析后追加:
- 选择质量:本次 §2 误退率较上次升降。
- D1:发现 skill/MCP 问题数、可执行建议数、归因完整度。
- D2:发现 wiki 幻觉/误解/不完整/不准确 各几处、建议是否落到具体页段、是否已转 /wiki-refine。
- 流程健康:有无递归/超时/解析失败;时长/规模。
- 下次建议:调打分阈值、补模板段、调 wiki 触点识别规则、补 fixture 等 → 反哺 §7/§8。

条目格式见该文件内的"维护协议"。

## 10. transcript / summary / 摩擦点 / 索引(同 v1/v2)

`transcript.md` 速览 + 逐轮流水,簿记行不入流水,长结果截断留 raw/,注入折叠,子会话递归链接。`summary.json` 指标 + `frictions[]`(tool_error/retry/permission_denied/user_correction[启发式]),排序固定可重现。`index.json` 每会话一条 + rollup,全量重算幂等;`INDEX.md` 人读版 + 警示。摩擦点是 D1 核心输入,也常是 D2(wiki 致跑偏)的线索。

## 11. 配置与探测

`EXPORT_ROOT` 首次询问记住;projects 根探测式(`$CLAUDE_CONFIG_DIR/projects`→`$HOME/.claude/projects`→`%USERPROFILE%\.claude\projects`,`--projects-root` 覆盖);`D:\wiki` 为 D2 wiki 根(仅按触点取被引段落比对,**不全量扫描**),`--wiki-root` 覆盖。

## 12. ⭐ 只评估"用户主动发起"的会话(v5)

三层:

**第 1 层 · 触发渠道即人类身份(主)**:仅当 **人类成员对该 issue 评论/@mention** 触发本 agent 才分析。`kind:comment` run 携带已认证发起者 + `trigger_comment_id`,等于"操作者=人"的硬证明——补上了 autopilot 给不了的那块。机器/agent 的自动 run 不会以"人类评论"形态触发本分析。(本地 hook 场景无此原生证明,靠第 3 层兜底。)

**第 2 层 · 自噬排除(防递归)**:
- 用 `issue runs.result.session_id` 定位会话时**排除 export-session 自己的 run**(不分析自己的会话)。
- 本 agent 回贴摘要时**不 @ 触发者、不 @mention 任何 agent**(遵守 mention 防循环),避免自己的评论又触发新一轮。
- 子代理 jsonl(`subagents/agent-*.jsonl`)本就不在 catalog 顶层扫描。

**第 3 层 · 会话级兜底**:分析前校验目标 session 是顶层会话、非空有实质轮次、cwd 不在排除名单、session_id ≠ 本 agent 自身 run;否则记日志跳过。

> 一句话:**人类评论/@mention = 用户发起的硬信号**(第 1 层,平台原生可证);第 2 层防自噬循环;第 3 层兜底(也是本地 hook 场景的主判据)。

## 13. ⚠️ 自动化护栏(v5)

1. **递归/自噬**:§12 第 2 层——排除自身 session_id + 回贴不 @mention + 子代理不入扫描。**上线前必须实现并单测。**
2. **频率闸门**:闸门=人类评论触发(§6/§12),不用规模阈值;纯空/中断会话可选跳过。
3. **尾部未落盘**:容错解析丢半行尾。
4. **并发**:多会话同时触发 → INDEX/eval-log 写入加文件锁或串行。
5. **失败静默**:失败写 `<EXPORT_ROOT>/.auto.log`,不静默吞错、不阻塞。
6. **文件可达性(关键)**:分析 agent 必须能读到被分析会话的 jsonl——需与产生该会话的 runtime **同机/共享文件系统**(`%USERPROFILE%\.claude\projects` 在固定 runtime 持久即可)。`issue runs` 也给出该 run 的 `runtime_id`/`work_dir`,可据此校验是否同机。

## 14. 编码与中文安全 / 测试策略

读 jsonl UTF-8;写 md/json UTF-8 **无 BOM**;slug 保留 CJK 去 `\/:*?"<>|`;引擎纯 Python(遵守 windows-cn-shell-safety)。TDD:pytest + 合成 fixtures,覆盖各行/块类型、空会话、超长截断、子代理/workflow、中文标题与路径、ai-title 回退、缓存失效;**确定性断言**(同输入+注入 exported_at→逐字节一致,无随机);score + 未选记录;**wiki_touch** 识别各类触点 + 取原文;**§12 三层**(人/机触发、自身 session_id 排除、空会话、回贴不 @mention);eval-log 追加幂等/并发锁。

## 15. 范围与非目标(v5)

**做**:任务完成后自动触发(分层,§6);经 `issue runs.session_id` / hook 定位会话;确定性导出;自动评估筛选 + 未选记录;**双维分析**(D1 skill/MCP 效果 + D2 会话内 wiki 使用保真度);AI 自维护自评;跨会话索引;摩擦点提取;只评估用户发起会话的三层过滤;护栏。

**不做**:自动删除/`--prune`;自动脱敏(仅警示);可视化 UI;数据库;实时流式;会话间 diff;**全量 wiki 扫描**(D2 只看会话触点);**自动改 wiki / 自动改 skill**——本技能只发现+建议,**改不改、怎么改都由人拍板**,wiki 维护走 /wiki-refine;**codex 会话**(phase 2)。

## 16. 已知风险 / 实现时确认

- **触发方式取舍**:主方案要用户多发一条评论/@mention;真·全自动需本地 SessionEnd hook 且同机可读 jsonl;轮询无法证明"已完成"是人点的。已按 §6 分层收敛。
- **D2 判定的可靠性**:幻觉/误解/wiki 致跑偏的判定是 LLM 判断,精度有限(尤其 agent 未显式引用 wiki 原文、靠"记忆"用 wiki 时,难定位被引段落);已定策略:拿不到确切被引原文时标"低置信疑似"而非硬判幻觉(§17.2)。
- **codex**:格式/路径不同,phase 2 独立 parser。
- **文件可达性**:见 §13.6,跨 runtime 时需共享/持久化。
- **token 体量**:大会话仍可能 10万~20万 token;以 summary/index 为主入口按需钻取。
- **脱敏缺位**:产物可能含密钥/内部 URL,仅警示。

## 17. 决策定案(原"待确认",v5 全部定案)

1. **触发方式** → **分层,默认主机制**:主=人对结束的 issue 发评论/@mention export-session(可靠满足"只评估用户发起",评论自带已认证人类发起者 + `trigger_comment_id`);真·全自动=本地 cc 的 `SessionEnd` hook(launcher 套 §12 过滤);兜底=scheduled-poll(最弱,无法证明"已完成"是人点的)。理由:§0 实测 autopilot 无状态/操作者事件触发,comment 是唯一"自带人类身份"的可靠 Multica 触发。
2. **D2 置信度策略** → **采用**。会话未显式引用 wiki 原文(凭记忆用)时,D2 标"低置信疑似",不硬判幻觉;以"wiki 触点能否取到确切被引原文"为置信门槛。
3. **session_id 定位前提** → **主用 `issue runs.result.session_id`**(本次已实测存在);同 `runtime_id`/`work_dir` 校验同机可读 jsonl(§13.6);本地非 Multica cc 回退 SessionEnd hook 注入 session_id。

## 18. 实现状态 / 交付物

**本 issue(SUP-4)已交付:**
- 本设计 **v5 定稿**(`export-session-design.md`,随 skill)。
- `SKILL.md` —— 行为规范(触发/定位/导出/筛选/模板/D1·D2 分析/自评/护栏),含"实现状态"说明。
- `references/analysis-template.md` —— 固定分析模板(可用,§8)。
- `export-session-eval-log.md` —— AI 自维护跨次自评记录文件,**已创建并初始化**(含维护协议 + bootstrap 条目),`.gitignore`。**直接满足本 issue 第 3 项要求"在 D:\jk_file\skills\ 下创建评估记录文件"。**
- `.gitignore` —— 忽略上面的 eval-log(决策 #11)。

**下一阶段(writing-plans / TDD,建议单开 issue):**
- 确定性 Python 引擎 `scripts/session_export/`(catalog/parse/render/summarize/score/wiki_touch/index/config),纯 stdlib、零 LLM、确定性可重现。
- `launcher`(取 session_id、护栏 §12/§13、串联引擎 + 受控分析调用)。
- `SessionEnd` hook 样例配置 + Multica 评论触发接线。
- pytest + 合成 fixtures(§14),先红后绿。

> 定稿完成即具备进入 writing-plans(TDD 分解)的一切前提:引擎 score / wiki_touch、launcher + 评论触发取 session_id、模板渲染(D1+D2)、§12 三层过滤、eval-log,先红后绿。
