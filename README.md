# Agent Skills

自定义的 Claude Code / Agent skills 仓库，围绕两条主线：

1. **业务系统 Wiki 体系** —— 以可配置的 wiki 根目录（默认 `D:\wiki`）为知识库，覆盖架构文档的生成、精炼、检索、生产问题速查与需求实现的完整闭环；
2. **Agent 工程实践** —— Windows 中文环境下的命令安全、堡垒机排查工具、session 质量监控。

## Skill 一览

### 业务系统 Wiki 体系

| Skill | 触发方式 | 用途 |
|-------|---------|------|
| [document-systems](document-systems/SKILL.md) | 手动 `/document-systems` | 为多模块仓库（Java / 前端 / Node / Python）的每个子系统生成中文架构文档；单系统仓库用 `--single` 生成单篇。附带 `scripts/wiki_engine` Python 引擎（解析 / 渲染 / lint / 域索引）。 |
| [wiki-refine](wiki-refine/SKILL.md) | 手动 `/wiki-refine` | document-systems 的伴生 skill。通过用户主导的对话，把业务知识深化补充进已生成的架构文档；子系统文档直接编辑，根文档以结构化建议方式提出修正。 |
| [wiki-search](wiki-search/SKILL.md) | 自动推断 | 帮 agent 高效检索 wiki 体系内容。适用三类场景：① 理解 FMS / VMOS / 港口云控相关仓库的架构、接口、配置或业务流程；② 故障排查、线上现象定位；③ 实现新功能前理解模块接口与依赖、评估改动风险。 |
| [prod-issue-quickref](prod-issue-quickref/SKILL.md) | 自动推断 + 手动 `/prod-issue-quickref add\|init` + Stop hook 唤起 | 维护并消费仓库级《生产问题速查.md》——「现象 → 根因」诊断决策树。用户报线上现象时按现象圈候选根因；排障 session 收尾时经「记录 / 询问门禁」把定位到的问题回流进速查。 |
| [spec-driven-implementation](spec-driven-implementation/SKILL.md) | 自动推断 | 把业务需求（PRD / spec / Jira / Confluence / docx / mhtml）转化为可工作的代码，尤其适合跨模块跨仓库、依赖外部库或数据源、与既有文档冲突、含内嵌图片/PDF、需求边做边变的场景。 |

### Agent 工程实践

| Skill | 触发方式 | 用途 |
|-------|---------|------|
| [windows-cn-shell-safety](windows-cn-shell-safety/SKILL.md) | 自动推断 | Windows 下涉及中文路径 / 中文文件名 / 非 ASCII 内容时的 Python 与 PowerShell 命令安全规则：解释器探测、路径安全、PowerShell 正则陷阱、CSV 清单写入，以及 Bash / PowerShell 工具边界。附带全局 PreToolUse hook（`hooks/`）。 |
| [cmdcap](cmdcap/SKILL.md) | 自动推断 | JumpServer 堡垒机 Luna Web 终端场景下的命令输出采集工具：目标机无法直连 SSH 时，把诊断命令的输出以文件形式带回给 agent。Go 实现（本仓库唯一含代码的目录，含测试与 Linux 二进制 `dist/`），详见其 [README](cmdcap/README.md)。 |
| [export-session](export-session/SKILL.md) | session 结束触发（Multica issue 评论 @mention 或本地 SessionEnd hook） | 导出并分析已结束的 Claude Code session：评估 skill / MCP 效果（D1）与 wiki 使用保真度（D2），产出 analysis.md 并维护跨运行自评日志。只发现和建议，不直接改 wiki / skill。 |

## 其他目录

- `plan/` —— 各 skill 的设计文档与实施计划（历史记录，不是 skill）。

## 安装方式

各 skill 通过 NTFS Junction 链接到 Claude Code 的 skills 目录，仓库内修改即时生效、无需复制：

```powershell
New-Item -ItemType Junction -Path "$env:USERPROFILE\.claude\skills\<skill-name>" -Target "D:\jk_file\skills\<skill-name>"
```

## 约定

- 每个 skill 目录必须有 `SKILL.md`（YAML frontmatter 提供 `name` 与 `description`，description 决定触发时机）。
- 较长的参考材料放 `references/`，可执行脚本放 `scripts/`，hook 配置放 `hooks/`。
- 文档正文以中文为主；frontmatter 的 description 按触发需要可中英混排。
