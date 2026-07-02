<!--
export-session 固定分析模板(template_version: 3)
用法:每次分析复制本骨架为 <EXPORT_ROOT>/<会话目录>/analysis/<时间戳_目标>/analysis.md。
骨架稳定,内容随分析过程分阶段填入(§1 筛选时实时写;§3/§4 分析时写;§2 收尾时回填)——
这就是需求所说"固定模板并在整个分析过程中不断调整"。
判定枚举、章节含义见 export-session-design.md §8。方括号 [...] 为待填占位。
-->
---
schema_version: 1
template_version: 3
analysis_goals: [skill_mcp_effectiveness, wiki_usage_fidelity]
session_id: [被分析会话 uuid]
source_jsonl: [~/.claude/projects/<编码cwd>/<session_id>.jsonl]
trigger: [comment | session_end_hook | schedule_poll]
trigger_comment_id: [若评论触发,人类作者的评论 id;否则 -]
wiki_root: D:\wiki
generated_at: [ISO8601 时间戳]
---

# 会话分析报告 — ([日期])

> ⚠ 本文件可能含密钥 / 内部 URL,复用或外传前请自查。
> 本报告仅为**发现 + 建议**;是否改、如何改由人拍板。wiki 修订走 /wiki-refine。

## 1. 选择决策(筛选阶段实时写)

自动评估筛选:标准 = "能否完成 D1/D2"。未选文件 + 当时不选原因**在筛选当时**即写入本表(设计 §7)。

| 文件 / 会话 | 选中? | 理由(打分信号:目标 skill/MCP 命中、摩擦点数、有无 wiki 触点、体量/预算) | 记录时刻 |
| -- | -- | -- | -- |
| [路径] | [是/否] | [理由] | [ts] |

## 2. 未选项事后评估(产出时回填)

对 §1 中每个"未选",在分析产出时回填当时不选是否合理(误退率反哺自评 §9 / 模板演进)。

| 未选文件 | 当时不选理由 | 事后评估(合理 / 误退) | 若应补选的影响 |
| -- | -- | -- | -- |
| [路径] | [理由] | [合理 / 误退] | [影响] |

## 3. D1 · skill/MCP 运行效果

摩擦点(错误 / 重试 / 权限被拒 / 用户纠正)归因 → 可监控的问题清单 + 可执行的改造建议。

| 摩擦点 | 位置(轮次/工具) | 归因 | 问题(可监控) | 改造建议(可执行) |
| -- | -- | -- | -- | -- |
| [现象] | [where] | [why] | [problem] | [suggestion] |

## 4. D2 · 本会话 wiki 使用保真度

对本会话每个 wiki 触点(由 wiki_touch 确定性标出),比对"agent 当时怎么用/怎么理解" vs "被引 wiki 原文"。
判定 ∈ {正确, 幻觉(编造/记错), 误解(曲解原文), wiki 不完整致跑偏, wiki 不准确致跑偏, **低置信疑似**}。
**无确切被引原文(凭记忆用 wiki)→ 标"低置信疑似",不硬判幻觉**(设计 §17.2)。

| wiki 触点(文件/页/调用) | agent 当时如何使用/理解 | 比对被引原文 | 判定 | 后果 | wiki 改进建议(具体到页/段,交 /wiki-refine) |
| -- | -- | -- | -- | -- | -- |
| [触点] | [用法] | [原文摘录/取不到则注明] | [判定] | [是否致偏差] | [建议] |

- 幻觉/误解:指出 agent 错在哪、是否造成偏差。
- wiki 不完整/不准确:指出 wiki 哪页哪段欠缺/有误、如何把 agent 带偏。

## 5. 结论与建议(D1 + D2 汇总,按优先级)

> 全部为**建议**,人拍板;wiki 类建议交 /wiki-refine。

1. [P0 建议]
2. [P1 建议]
3. [...]

## 6. 与历史对比摘要

- 相对上次:误退率 [↑/↓]、D1 问题/建议数 [变化]、D2 各判定处数 [变化]、流程健康 [有无递归/超时/解析失败]。
- 详见自评记录:`D:\jk_file\skills\export-session\export-session-eval-log.md` 本次条目。
