---
name: export-session
description: 'Export and analyze a FINISHED Claude Code session for skill/MCP effectiveness (D1) and in-session wiki-usage fidelity (D2). Triggered automatically at session end — via a human comment/@mention on the finished Multica issue (primary) or a local SessionEnd hook — NOT inferred from natural language. Deterministically exports the session JSONL, auto-selects which sessions/files to analyze (recording every unselected file and why, at selection time), writes an analysis.md from a fixed evolving template, and maintains an AI-owned cross-run self-eval log at D:\jk_file\skills\export-session\export-session-eval-log.md. Discover-and-suggest ONLY — it never edits wiki/skills; humans decide, and wiki fixes go through /wiki-refine. North star: automated maintenance of a high-quality wiki (D:\wiki) + skill/MCP problem monitoring.'
---

# export-session

会话导出分析技能。一段 Claude Code 会话**结束后自动触发**,把该会话的 JSONL 确定性导出为可读产物,再做一次受控分析,产出**双维分析文档**(D1 skill/MCP 效果、D2 会话内 wiki 使用保真度),并维护一份 **AI 自维护的跨次自评记录**。**只发现 + 建议,改不改/怎么改一律由人拍板**;wiki 的实际修订走 `/wiki-refine`。

## ⚙️ 能力构成

- ✅ 行为规范(本文件)、固定分析模板(`references/analysis-template.md`)、自评记录文件(`export-session-eval-log.md`,已初始化)、`.gitignore`。
- ✅ **确定性导出引擎**:`scripts/session_export/`(`config` / `parse` / `render` / `summarize` / `catalog` / `index` + `export` 编排 + `__main__` CLI),纯 stdlib、零 LLM,注入 `exported_at` 后逐字节可复现。
- ✅ **筛选 / D2 触点 / 编排 / 触发**:
  - `score` —— 按"能否完成 D1/D2"自动筛选;**未选文件 + 当时不选原因在筛选当时**(带 `recorded_at`)落 `analysis.md` §1,产出时回填 §2。
  - `wiki_touch` —— 确定性标出 wiki 触点(读 `D:\wiki` 的 `Read/Grep/Glob`、抓 wiki 的 `WebFetch`、`mcp__ones_wiki__*`、`document-systems`/`wiki-refine` 使用)并抓取被引 wiki 原文;拿不到确切原文标"低置信疑似"(§17.2)。
  - `analyze` —— 按模板渲染 D1+D2 `analysis.md`(确定性);默认基线分析器可注入替换为一次 LLM 受控分析(launcher 的 `analyzer` 形参)。
  - `evallog` —— 向 `export-session-eval-log.md` 追加一条(本次 vs 历次),**幂等 + 文件锁**(§13.4)。
  - `launcher` —— 取 `session_id`(`issue runs.result.session_id` / hook 注入)、**§12 三层过滤 + §13 防自噬护栏**、串联引擎 + 一次受控分析。CLI:`python -m session_export analyze …`。
  - 触发接线见 `references/triggers.md`(本地 `SessionEnd` hook 样例 + `references/hooks/session_end_hook.py`;Multica 评论/@mention 路径)。
- ✅ pytest 全绿(`scripts/tests/`,117 项);跑法见 `scripts/README.md`。

## 触发方式(不从自然语言推断)

本技能是**自动化技能**,只应由以下渠道拉起,**不要**因为用户在对话里提到"会话""导出""分析"就推断调用:

1. **主(Multica)**:用户对**已结束的 issue** 发一条评论 / `@mention export-session`。该 run 为 `kind:comment`,平台注入**已认证的人类发起者** + `trigger_comment_id` —— 这既是"任务已结束"的信号,也是"用户主动发起"的硬证明。
2. **真·全自动(本地 cc)**:`settings.json` 的 `SessionEnd` hook → launcher;hook 直接注入 `session_id`。
3. **兜底(最弱)**:scheduled autopilot 轮询近段"已完成"的 issue(无法证明是人点的,尽力而为)。

平台前提(实测,设计 §0):`autopilot trigger-add` 只有 `schedule|webhook`,**裸改 issue 状态不触发任何 run**;能触发且自带人类身份的是**评论/@mention**。故触发不走"标已完成 → autopilot"。

## 参数

- `--projects-root <path>` — 覆盖 `~/.claude/projects` 探测。
- `--wiki-root <path>` — D2 的 wiki 根,默认 `D:\wiki`。
- `--export-root <path>` — 覆盖 `EXPORT_ROOT`(默认 `D:\claude-sessions`,首次询问记住)。
- `--session-id <uuid>` — 直接指定被分析会话(本地 hook 场景由 hook 注入)。
- `--no-raw` — 不落 `raw/` 原始截断内容。

## 硬约束(main agent 与所有子代理)

- **只发现 + 建议**:绝不自动改 `D:\wiki` 或任何 skill;是否改、如何改由人决定。wiki 修订建议交 `/wiki-refine`。
- **防自噬循环**:定位会话时排除 export-session 自己的 run(按 `session_id`);回贴摘要时**不 @ 触发者、不 @mention 任何 agent**;子代理 jsonl 不入顶层扫描。
- **只评估用户主动发起的会话**:见"只评估用户发起"三层过滤;拿不到人类发起证明且会话级校验不通过时,记日志跳过,不分析。
- **确定性**:引擎落地后,同输入 + 注入 `exported_at` → 产物逐字节一致;零随机、零 LLM 于导出层。
- **中文/编码安全**:读 jsonl UTF-8;写 md/json UTF-8 **无 BOM**;遵守 `windows-cn-shell-safety`。
- **不阻塞、不静默吞错**:失败写 `<EXPORT_ROOT>/.auto.log`。

## 流程

### Phase 0 — 护栏与"用户发起"判定

先判是否应分析(设计 §12):
1. **触发渠道即人类身份(主)**:仅当**人类成员评论/@mention** 触发才继续;`kind:comment` + `trigger_comment_id` 即证明。机器/agent 自动 run 不以此形态触发。
2. **自噬排除**:目标会话 `session_id` ≠ export-session 自身任何 run 的 `session_id`;cwd 不在排除名单。
3. **会话级兜底**:目标 session 是顶层会话、非空有实质轮次;否则记日志跳过。

不通过 → 写 `.auto.log` 并退出(成功退出,不报错、不 @mention)。

### Phase 1 — 定位会话

- **Multica 评论触发**:`multica issue runs <issue-id> --output json` → 取本次**工作 run 的 `result.session_id`**(实测该字段存在;排除 export-session 自己的 run;多 run 取相关工作 run)。`runtime_id`/`work_dir` 校验同机可读(设计 §13.6)。
- **本地 hook**:直接用注入的 `--session-id`。
- 据 `session_id` 定位 `~/.claude/projects/<编码cwd>/<session_id>.jsonl`。

### Phase 2 — 确定性导出 + 打分 + wiki 触点

引擎(`scripts/session_export/`),整条 `analyze` 已把以下串起来:
- ✅ `catalog/parse/render/summarize/index` → `transcript.md` + `summary.json`[+ `raw/`] + 跨会话 `INDEX.md`/`index.json`,簿记/注入/超长按设计 §3/§10 处理。
- ✅ `score` → 自动评估筛选 `{选中, 未选 + 当时不选原因}`;**未选文件 + 原因(带 `recorded_at`)在此刻即写入 `analysis.md` §1**(设计 §7)。
- ✅ `wiki_touch` → 确定性标出会话中的 **wiki 触点**(读 `D:\wiki` 文件、抓 wiki 的 WebFetch、`mcp__ones_wiki__*` 调用、document-systems/wiki-refine 使用等)并抓取被引 wiki 原文。

一步跑通(hook 路径):`python -m session_export analyze --session-id <id> --projects-root <P> --export-root <E> --wiki-root D:\wiki`;评论路径用 `--issue-id <id> --self-agent-id <本 agent id>`。仅导出请用 `export` 子命令。

### Phase 3 — 一次受控分析(按固定模板)

以 `references/analysis-template.md` 为骨架,内容随过程累积:
- a) 确认/修正筛选(理由续记 §1)。
- b) **D1 · skill/MCP 效果**:摩擦点(错误/重试/权限/用户纠正)归因 → 问题清单(可监控)+ 改造建议(可执行)。
- c) **D2 · 会话内 wiki 使用保真度**:对每个 wiki 触点,比对"agent 当时怎么用/怎么理解" vs "被引 wiki 原文",判定 ∈ {正确, 幻觉, 误解, wiki 不完整致跑偏, wiki 不准确致跑偏, 低置信疑似}。**无确切被引原文(凭记忆用 wiki)→ 标"低置信疑似",不硬判幻觉。** wiki 改进建议具体到页/段,交 `/wiki-refine`,人拍板。
- d) 收尾回填 §2"未选项事后评估"(当时不选是否合理)。

产物:`<EXPORT_ROOT>/<会话目录>/analysis/<时间戳_目标>/analysis.md`。

### Phase 4 — 索引 + 自评 + 回报

- `index` → 重算 `INDEX.md` / `index.json`(全量幂等)。
- **自评**:向 `export-session-eval-log.md` 追加一条(本次 vs 历次,D1/D2,流程健康,下次建议),遵守该文件内"维护协议"。并发写加文件锁/串行。
- **回报**:输出 `analysis.md` 路径;评论场景可回贴一段简短摘要,**但不 @ 触发者、不 @mention 任何 agent**(防循环)。

## 只评估"用户发起"的会话(三层)

| 层 | 判据 | 覆盖场景 |
| -- | -- | -- |
| 1 触发渠道即人类身份 | `kind:comment` + `trigger_comment_id`(人类作者) | Multica 评论/@mention(主) |
| 2 自噬排除 | `session_id` ≠ 自身 run;回贴不 @mention;子代理不入扫描 | 防递归烧钱 |
| 3 会话级兜底 | 顶层会话、非空实质轮次、cwd 不在排除名单 | 本地 hook 主判据 + 通用兜底 |

## 本技能不做

- 不自动删除 / `--prune`;不自动脱敏(仅警示)。
- 不做全量 `D:\wiki` 扫描(D2 只看会话触点)。
- **不自动改 wiki / 不自动改 skill**;不生成可视化 UI / 数据库 / 实时流。
- 不处理 codex 会话(phase 2)。

## 相关

- `references/triggers.md` —— 触发接线:本地 `SessionEnd` hook 样例 + Multica 评论/@mention 路径(设计 §6)。
- `references/analysis-template.md` —— 固定分析模板(D1+D2,`template_version 3`)。
- `/wiki-refine` —— 本技能 D2 发现的 wiki 问题的实际维护出口(人驱动)。
- `windows-cn-shell-safety` —— 引擎/脚本的中文与编码约束。
- `../plan/export-session-design.md` —— 完整设计与决策记录(v5)。
