# export-session 会话导出技能设计

> 状态:**v1 — brainstorming 收敛定稿,待用户审阅 spec 后进入 writing-plans**(创建 2026-06-18)
> 范围:本次只设计并实现"导出 + 编目 + 索引"。**分析本身**(提炼脚本 / 评估 skill·MCP / 提炼新 skill 等)是导出产物的下游用途,由用户后续另开对话完成,不在本技能内。
> 配套:由 brainstorming 对话收敛而来;格式、选择方式、内容粒度、4 个开放点均经用户确认(见 §2)。
> 工程路线沿用 `wiki-engine`:确定性 Python 引擎 + 薄 skill 驱动 + TDD。

***

## 1. 背景与问题

Claude Code 的会话以 JSONL 存于 `~/.claude/projects/<编码后的cwd>/<session-uuid>.jsonl`,并在同名子目录下存子代理 / workflow 转写(`subagents/agent-*.jsonl`、`subagents/workflows/wf_*/...`)。直接使用这些原始文件做分析有三个硬伤:

1. **多文件**:一个会话不是单文件,是"主 jsonl + 子目录"。
2. **噪音淹没信号**:`file-history-snapshot`(每次编辑存整份文件)、`attachment`(注入文件全文 / system-reminder / base64 图片)、`mode`/`permission-mode`/`last-prompt`/`ai-title` 等簿记行占了大半体积。本仓最大会话 3.3MB / 1034 行,原样喂模型约 80 万~100 万 token。
3. **文件名是裸 UUID**:无标题、无日期,无法人工挑选。

**目标**:把可确定化的"解析 + 清洗 + 渲染 + 编目 + 索引"做成确定性 Python 引擎,产出对 Claude 友好的分析素材;LLM 只负责"选会话、确认选项、之后做真正的分析"。

**消费者是 Claude(LLM)本身**,用途见 §2 决策 0 引用的 5 类场景。这决定了格式选型(§3)。

## 2. 已锁定决策(用户已确认)

| #  | 决策                | 内容 |
| -- | ----------------- | --- |
| 0  | 用途与消费者            | 导出物供 Claude 分析,用于:① 提炼自动运维脚本;② 梳理/改进第三方平台(MCP)工具调用;③ 评估当前 skill/MCP 运行效果并提改造建议;④ 梳理运维经验(让 AI 更全自动);⑤ 提炼新 skill。 |
| 1  | **存储格式 = 混合**      | 每会话:`transcript.md`(清洗后流水,主分析对象)+ `summary.json`(结构化指标,跨会话聚合)+ 可选 `raw/`(原始 jsonl,无损保底)。**不是单一格式**——叙事用途要 MD,评估/聚合用途要 JSON。 |
| 2  | **选择方式 = 跨项目交互式勾选** | 扫描所有 project 目录 → 列清单(日期/项目/标题/skill·MCP/大小)→ 用户勾选一个或多个。理由:评估 skill/MCP 效果天然跨项目。 |
| 3  | **内容粒度**           | 默认**含** thinking 推理块、子代理/workflow 子会话(存独立文件 + 主流水链接);默认**裁** 文件快照、system-reminder、超长工具结果(截断,原文留 raw/)、注入文件(折叠为一行摘要)。 |
| 4  | **架构 = 确定性引擎**     | JSONL→产物 的转换零 LLM 参与。skill 层只编排。沿用 wiki-engine 的"引擎 + 驱动 + TDD"。 |
| 5  | EXPORT_ROOT       | 默认 `D:\claude-sessions`,**首次运行询问并记住**(同 document-systems 的 wiki 根做法)。 |
| 6  | raw/ 默认开           | 默认拷贝原始 jsonl 做无损保底(支持以后改进渲染后重导);`--no-raw` 关闭。 |
| 7  | 脱敏                | v1 **不自动脱敏**,仅在 INDEX 顶部加安全警示;以后按需加 `--redact`。 |
| 8  | 生命周期 = 极简(YAGNI)   | 每个导出带 `status`(active/archived)+ `tags` + `notes` 字段,加跨会话索引。**删除不进 skill**(误删风险),留用户手动;以后再考虑 `--prune`。 |

## 3. 总体架构

```
┌─ 技能层(SKILL.md,薄)──────────────────────────────────┐
│ /export-session(手动命令,带"不从自然语言推断"护栏):       │
│   解析 flag → 调引擎编目 → 列清单让用户勾选 →               │
│   调引擎导出 → 报告产物路径。不读会话内容、不做转换。          │
├─ 引擎层(export-session/scripts/session_export/,3.8+ stdlib)┤
│  catalog  : 扫描所有 project,产出会话清单(带缓存)            │
│  parse    : 容错解析主 jsonl + 子代理/workflow                │
│  render   : → transcript.md(清洗/截断/折叠/链接子会话)        │
│  summarize: → summary.json(指标 + 摩擦点)                    │
│  index    : 重算 INDEX.md / index.json(含跨会话 rollup)      │
│  config   : 解析/记住 EXPORT_ROOT,探测式定位 projects 根      │
└────────────────────────────────────────────────────────┘
```

技能目录布局(对齐现有 skill 结构):

```
export-session/
├─ SKILL.md
├─ scripts/session_export/        # 引擎(纯 stdlib)
│   ├─ __init__.py  catalog.py  parse.py  render.py  summarize.py  index.py  config.py  cli.py
└─ tests/                         # pytest + 合成 jsonl fixtures
```

## 4. 数据流

```
/export-session [flags]
  1. config: 确定 EXPORT_ROOT(首次询问)、探测 projects 根
  2. catalog: 扫所有 project 的顶层 *.jsonl(不含子目录里的 agent-*.jsonl)
        每个会话抽取: id / project / title(末条 ai-title,缺则首条用户提问截断)
        / 起止时间 / 用到的 skill·MCP / 行数·字节
        结果按 (路径, mtime, size) 缓存到 <EXPORT_ROOT>/.catalog-cache.json
  3. select: skill 层列清单 → 用户勾选编号(或由 flag 直接给定 id/过滤)
  4. export: 对每个选中会话
        parse → render(transcript.md) + summarize(summary.json) [+ raw/]
        子代理/workflow 递归渲染为 subagents/*.md
        若该会话曾导出: 沿用旧 summary.json 的 lifecycle(status/tags/notes)
  5. index: 重算 INDEX.md / index.json(扫描 EXPORT_ROOT 下所有 summary.json)
  6. report: 输出每个产物的绝对路径
```

## 5. 产物布局

```
<EXPORT_ROOT>/
├─ INDEX.md                       # 人读总览表 + rollup
├─ index.json                     # 机读: 每会话一条 + 跨会话 rollup
├─ .catalog-cache.json            # 编目缓存(加速重复扫描)
├─ .config.json                   # 记住的 EXPORT_ROOT 等(见 §10)
└─ 2026-06-18_导出session设计_ad2180ec/
   ├─ transcript.md               # 顶部"速览" + 逐轮流水(主分析对象)
   ├─ summary.json                # 单会话指标 + 摩擦点 + lifecycle
   ├─ subagents/
   │   ├─ agent-a4d713_Explore.md
   │   └─ workflows/wf_41938e/agent-*.md
   └─ raw/                        # 默认开
       ├─ <id>.jsonl
       └─ subagents/...           # 原样拷贝子目录
```

**文件夹命名**:`YYYY-MM-DD_<标题slug>_<id前8位>`。slug 规则:去 Windows 非法字符 `\/:*?"<>|`、空白折叠为 `_`、保留 CJK、截断约 40 字符;标题为空则用首条用户提问;仍为空则 `untitled`。

## 6. `transcript.md` 结构

```markdown
---
session_id: ad2180ec-...
title: 导出 session 设计
project: D--jk-file-skills
cwd: D:\jk_file\skills
git_branch: master
schema_version: 1
exported_at: 2026-06-18T11:50:00Z
---

# 导出 session 设计

## 速览
- 项目 D--jk-file-skills · cwd D:\jk_file\skills · 分支 master
- 起 11:02:13 — 止 11:48:55 · 时长 46.7 min · model claude-opus-4-8[1m]
- 轮次 37 · 工具调用 90
- skills: brainstorming×1
- MCP: ones_wiki.export×2 (1 err)
- ⚠ 摩擦点 3(详见末尾 / summary.json)
- 改动文件: engine.py, MIGRATION.md

## 对话

### 1 · user · 11:02:13
帮我导出会话…

### 2 · assistant · 11:02:18
_(thinking)_ 用户想要把会话存成…           ← 默认含,--no-thinking 可去
好的,我先列出会话文件…
- ▸ **Skill** `brainstorming` → ok
- ▸ **Bash** `ls *.jsonl` → 7 files (ok)
- ▸ **Task→Explore** ↳ [subagents/agent-a4d713_Explore.md](subagents/agent-a4d713_Explore.md)
- ▸ **Edit** `engine.py` → ok
- ▸ **Bash** `pytest -q` → [截断 38 行,完整见 raw/](raw/...)

…

## 摩擦点
1. 轮 14 · 工具报错 · Bash gbk 编码 · 已恢复
2. 轮 22 · 用户纠正(启发式) · "不对,应该…"
```

**渲染规则**:
- **轮 = 按时间顺序的每条 user/assistant 消息**;簿记行(mode/last-prompt/ai-title/file-history-snapshot)不入流水。
- 工具调用渲染在发起它的 assistant 消息下,显示 `工具名 + 入参摘要 + → 结果摘要 + (ok/err)`。
- **截断**:工具结果超过 40 行或 2000 字符(先到为准)→ 保留开头 + `[截断 N 行,完整见 raw/]`。`--full-results` 关闭截断。
- **折叠**:注入文件/attachment → 一行摘要 `[注入 X.java,320 行]`。
- **子会话**:Task/Agent/Workflow 的发起处插入相对链接,子会话本身递归用同样规则渲染为 `subagents/*.md`。映射按发起顺序/时间戳尽力对齐;无法确定时在末尾"子会话"段统一列出。

## 7. `summary.json` 字段

```json
{
  "schema_version": 1,
  "session": {
    "id": "ad2180ec-...", "title": "导出 session 设计",
    "project": "D--jk-file-skills", "cwd": "D:\\jk_file\\skills",
    "git_branch": "master",
    "start": "2026-06-18T11:02:13Z", "end": "2026-06-18T11:48:55Z",
    "duration_min": 46.7, "models": ["claude-opus-4-8[1m]"], "cc_version": "..."
  },
  "counts": { "turns": 37, "user_msgs": 12, "assistant_msgs": 25, "tool_calls": 90 },
  "skills":    [ {"name": "superpowers:brainstorming", "calls": 1} ],
  "mcp_tools": [ {"name": "ones_wiki.export_ones_wiki_page_markdown", "calls": 2, "errors": 1} ],
  "tools":     [ {"name": "Bash", "calls": 40, "errors": 2}, {"name": "Edit", "calls": 12, "errors": 0} ],
  "tokens":    { "input": 812000, "output": 45000, "cache_read": 0, "cache_creation": 0 },
  "files_touched": ["engine.py", "MIGRATION.md"],
  "subagents": [ {"file": "subagents/agent-a4d713_Explore.md", "type": "Explore"} ],
  "frictions": [
    {"turn": 14, "kind": "tool_error", "tool": "Bash", "detail": "gbk codec error", "recovered": true},
    {"turn": 22, "kind": "user_correction", "heuristic": true, "detail": "用户指出 X 不对"}
  ],
  "lifecycle": { "status": "active", "tags": [], "notes": "", "exported_at": "2026-06-18T11:50:00Z" }
}
```

排序固定(可重现):`skills`/`tools`/`mcp_tools` 按 calls 降序再名字升序;`files_touched` 字典序。

## 8. ⭐ 摩擦点检测(确定性提取,本设计的增值项)

评估 skill/MCP 最值钱的信号是"哪里出了摩擦"。`frictions[]` 由引擎确定性提取:

- `tool_error`:`tool_result` 带错误标记(is_error / 错误前缀)。
- `retry`:报错后对同一工具的近似重复 `tool_use`。
- `permission_denied`:权限被拒。
- `user_correction`(**启发式,标 `heuristic:true`**):报错或 assistant 输出后,紧跟的、含"不对/错了/不是/应该/重来/wrong/no"等线索的用户消息。精度有限,仅作信号。

摩擦点同时进 `summary.json`、`transcript.md` 末尾和顶部速览高亮。

## 9. 跨会话索引与聚合

`index.json` = 每个导出会话一条记录(从各 `summary.json` 收集)+ 一个 `rollup`:

```json
"rollup": {
  "by_skill": [ {"name": "document-systems", "sessions": 4, "calls": 9, "errors": 1, "avg_frictions": 2.0} ],
  "by_mcp":   [ {"name": "ones_wiki.export...", "sessions": 3, "calls": 7, "errors": 2} ]
}
```

每次导出后**全量重算**(扫 EXPORT_ROOT 下所有 summary.json,幂等)。`INDEX.md` 是其人读版:一张表(日期/项目/标题/skills/mcp/工具数/摩擦/tokens/status/文件夹链接)+ rollup 段 + 顶部脱敏安全警示。

→ 这直接服务"评估某 skill/MCP 改进前后效果":schema 稳定,多次导出可纵向比 rollup。

## 10. 配置与探测

- `EXPORT_ROOT`:首次运行询问,存到固定配置(`~/.claude` 下或 skill 约定位置),`--reconfigure` 重设。
- **projects 根探测式定位**(不硬编码 `C:\Users\admin`):依次试 `$CLAUDE_CONFIG_DIR/projects` → `$HOME/.claude/projects` → `%USERPROFILE%\.claude\projects`;`--projects-root` 可覆盖。适配换机 / codex / CI。
- 项目目录名 = cwd 的编码(`: \ / _ .` → `-`);`--current`/`--project` 时把传入 cwd 同样编码后匹配。

## 11. 调用与默认值

`/export-session`(手动 slash 命令,带"仅在用户精确输入命令时触发、不从自然语言推断"护栏)。

| flag | 作用 |
| --- | --- |
| (无参) | 跨项目列清单交互勾选 |
| `<id> [<id>…]` | 直接按 session id 导出 |
| `--current` | 导出当前会话(= 当前项目目录下 mtime 最新的顶层 jsonl;**注:导出活动会话不含触发导出的本轮**) |
| `--since <date>` / `--skill <name>` / `--project <name>` | 过滤批量导出 |
| `--no-raw` / `--no-thinking` / `--no-subagents` / `--full-results` | 内容粒度开关 |
| `--reconfigure` / `--projects-root <path>` | 配置 |

默认值:跨项目列清单、thinking 含、子代理含、raw 含、长结果截断、注入文件折叠。

**重复导出**:已导出会话再导 → 覆盖其文件夹,index 按 id 原地更新,`exported_at` 刷新;**lifecycle(status/tags/notes)从旧 summary.json 沿用,不被覆盖**。`--skip-existing` 可跳过已存在。

## 12. 编码与中文安全(遵守 windows-cn-shell-safety)

- 读 jsonl 一律 UTF-8;写 md/json 一律 UTF-8 **无 BOM**。
- 文件夹/文件名 slug 见 §5;保留 CJK,去非法字符。
- 引擎纯 Python、不经 PowerShell 处理内容,规避 GBK / `\U` 等坑。

## 13. 测试策略(TDD,先红后绿)

- pytest + 合成 jsonl fixtures,覆盖:每种行类型(assistant/user/system/attachment/file-history-snapshot/…)、每种内容块(text/thinking/tool_use/tool_result)、空会话、超长结果截断、子代理、workflow、中文标题与路径、缺失 ai-title 的标题回退、缓存命中/失效。
- **确定性断言**:给定(输入文件,注入的 `exported_at`),两次渲染逐字节一致;无 `Date.now`/随机;排序固定。
- 摩擦点检测各分支单测。
- catalog 缓存按 (mtime,size) 失效的单测。

## 14. 范围与非目标(YAGNI)

**做**:导出(MD+JSON+raw)、跨项目编目交互选择、跨会话索引+聚合、摩擦点提取、极简生命周期字段。

**不做(v1)**:自动删除/`--prune`、自动脱敏、可视化 UI、数据库、实时流式导出、会话间 diff 工具、**分析本身**(提炼脚本/评估/提炼 skill 均为下游另开对话完成)。

## 15. 已知风险/待实现时确认

- **子会话↔发起工具的映射**:数据里 Task/Agent 的 tool_use 与子代理 jsonl 的关联可能需按时间戳/顺序启发式对齐;不确定时降级为末尾统一列出。
- **`--current` 的当前会话识别**:优先由 skill 层传入当前 session id;无则回退"当前项目最新 mtime"。
- **token 体量**:即使清洗后大会话 transcript 仍可能 10 万~20 万 token;跨会话分析应以 `summary.json`/`index.json` 为主入口,按需再钻取 transcript。
- **脱敏缺位**:导出物可能含密钥/内部 URL;v1 仅警示不打码,复用/外传前用户自行注意。
