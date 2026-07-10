---
name: prod-issue-quickref
description: 维护并消费「生产问题速查.md」——一个仓库级的「现象 → 根因」诊断决策树（放在 wiki 体系里 <domain>/<repo>/生产问题速查.md，wiki 根由 document-systems 运行时解析）。三种触发：(1) 用户报线上现象 / 问「这个现象可能是什么原因」时，读该仓速查、按现象圈候选根因并指导确认；(2) 用户显式 /prod-issue-quickref add|init 手动维护；(3) 一次「分析定位问题」的 session 收尾、被 Stop hook 的提示唤起时，走「记录 / 询问门禁」把本次定位到的问题记入对应速查（不确定就先问用户）。当用户提到 生产问题速查 / 现象速查 / 把这个问题记进速查 / add to quickref、或在做生产问题定位排障时使用。
---

# prod-issue-quickref

维护并消费**仓库级诊断决策树**「生产问题速查.md」：按现象快速圈定几个候选根因、指导程序员去对应 wiki / 代码确认。**只做定位分诊，不做完整分析**——完整链路 / 证据 / 修复放在被链接的 wiki 文档里。

文档形态、节点规则见 `references/tree-template.md` 与 `references/node-format.md`（动手前先读）。校验器 `scripts/validate_quickref.py`，会话 hook `scripts/quickref_hook.py`。
**条目层**（单问题完整记录：现象/定位步骤/根因/解决升级/三类判定/可复用性）与回流、生命周期/过期规则见 `references/entry-template.md`——速查树只分诊，完整记录进 `<DOC_ROOT>/issue/` 条目，两层由本 skill 统一管理。

## 1. 定位文档（每种操作先做）

1. 读 `%USERPROFILE%\.document-systems.json` 取 `wiki_base`（缺失 / 空则按 document-systems 的默认逻辑回退，不要在此写死盘符）。
2. `REPO_ROOT` = `git rev-parse --show-toplevel`（不在 git 里则当前目录）；`REPO_NAME` = 其 basename。
3. 解析域（复用现成引擎，别重造）：
   `python -X utf8 <ENGINE_CLI> resolve-domain --repo <REPO_ROOT> --wiki <WIKI_BASE>` → 取 JSON 的 `domain`。
   `<ENGINE_CLI>` 探测顺序（禁写死用户名）：`<repo>/document-systems/scripts/wiki_engine/cli.py` → `%USERPROFILE%\.claude\skills\document-systems\scripts\wiki_engine\cli.py` → 配置里指定的安装根。
4. `DOC_ROOT = <WIKI_BASE>/<DOMAIN>/<REPO_NAME>`；`QUICKREF = <DOC_ROOT>/生产问题速查.md`。
   （例：源码仓 fabusurfer → `domain=old_project` → `QUICKREF = <WIKI_BASE>\old_project\fabusurfer\生产问题速查.md`。所有路径都用 `<WIKI_BASE>`/`<DOC_ROOT>` 等解析出的变量，不写绝对盘符。）

## 2. 消费（读，最常用）

用户报**线上现象**、或问「这个现象可能是什么原因」时：定位 `QUICKREF`（§1）→ 读它 → 在树里按现象找匹配的 `##` 共有现象根 → 沿「**判别**」分支逐层收窄 → 到「**根因**」叶子给出候选根因 + 「判别信号」教用户怎么确认 → 打开叶子里链接的 wiki 文档核对。**只读不改**。找不到匹配现象 → 如实说「速查里暂无此现象」，正常排障；排障中若定位到了根因，收尾按 §4 记录。

## 3. 记录（add：手动与自启动共用同一套追加逻辑）

已从本次定位得到：`共有现象`、`判别信号`、`一句话根因`、根因所在 `子系统/接口/表` 标识。然后：

1. **解析确认链接**：在 `<DOC_ROOT>` 内按子系统 / 接口 / 类 / 表名匹配已存在的 wiki 文档 + 锚点——优先 `<子系统>/architecture.md` 的相关 `§`，其次该子系统下的 troubleshooting / runbook，再 `_common/`。锚点用引擎 `outline` / `refs` 或 grep 目标标题按 GitHub slug 规则算。**找不到深度文档**：仍写一句话根因 + 链到最接近的架构章节，并提示「该根因暂无深度 wiki 文档，建议后续补」（不在此自动写深度文）。
2. **find-or-create**：无 `QUICKREF` → 先按 §5 `init`；有 → 读现有树。
3. **定落点**（去重优先）：
   - 树里有匹配的 `##` 共有现象根 → 在其下**加一条 `- **判别** → 根因` 分支**；若已存在等价判别/根因，**合并或跳过**，别造重复节点。
   - 无匹配现象根 → **新起一个 `## <共有现象>` 根**，再加分支。
4. **写入**：用 file-write / Edit，全程 UTF-8；同时把 frontmatter `updated` 改成今天。节点严格按 `references/node-format.md`：现象自然语言可归纳；根因叶子 + 判别里的代码/日志标识**原样**；叶子**必须**带 `](....md)` 确认链接；**禁**写恢复步骤 / 待确认 / 证据 / 时间线。
5. **必跑校验**：`python -X utf8 scripts/validate_quickref.py <QUICKREF>`。
   - 手动场景：不过则据报错修好再落定，并 `git -C <WIKI_BASE> diff` 让用户看改动。
   - 自启动场景（无人当场复核）：不过则**回滚本次编辑**、把要点如实告诉用户「校验没过，没落盘，请手动确认」，不要硬写。
6. **判断是否建条目**（条目层，规则见 `references/entry-template.md`）：本次定位有完整证据链（定位步骤 + 解决/升级去向）→ 按其 §2 模板在 `<DOC_ROOT>/issue/` 建条目并与速查叶子互链、做三类结果判定；只有一句话根因（移交即终态类）→ 显式声明「速查分支即终态」即可。同类复发不新开条目，原条目 `occurrence_count +1`。

## 4. 记录 / 询问门禁（自启动被 Stop hook 唤起时执行）

被 Stop hook 的提示唤起后，判断并三选一：
- **有把握 → 直接记**：本 session 明确定位到一个**值得记录**的生产问题根因（有现象 + 定位到根因 + 有可链接的 wiki 文档）→ 走 §3 追加，并简短告诉用户「已记入速查：<现象→根因>」。
- **不确定 → 先问**（用户明确要求）：定位不完整 / 不确定是否算生产问题 / 不确定是否值得沉淀 → 用 `AskUserQuestion` 问：「这次定位到的『<现象>→<根因>』要不要记进 生产问题速查.md？」→ 是则 §3 记、否则跳过。
- **明确不记**：本 session 并非问题定位、或没定位到明确根因 → 静默结束，不记不问。

原则：**能确信才自动记，其余一律先问；把「漏问」看得比「多问一次」更糟，但绝不静默瞎记。** 若你是**非交互的自动化 agent**（后台 / 任务运行，无法交互提问）：能确信就记，否则直接结束，不要卡在提问上。

## 5. init（空树脚手架）

以 `references/tree-template.md` 生成 `<DOC_ROOT>/生产问题速查.md`：填 `title` / `scope` / 日期 / `tags` / repo 名，保留顶部「用法 / 记录约定 / 新增」四条说明，**不含任何 `## 现象` 根**（空树），删掉模板里的占位注释。

## 6. 自启动接线（安装时一次性，属配置变更）

自启动靠 Claude Code hooks（一个 prose skill 不能自触发）：把 `hooks.settings.snippet.json` 的 `hooks` 块合并进 `%USERPROFILE%\.claude\settings.json`（合并时把命令里的 `%USERPROFILE%` 换成本机真实绝对路径——hook 命令未必展开环境变量；这条绝对路径落在**用户本机 config**、不属于 skill 制品）——
- `PostToolUse`(matcher `Read`) → `quickref_hook.py --arm`：读过某仓 `生产问题速查.md` 就**布防**本 session；
- `Stop`(matcher `""`) → `quickref_hook.py --stop`：已布防且未处理过时，`{"decision":"block","reason":…}` 把模型多推一轮来走本文件 §4。
hook 脚本**fail-open**（任何异常都放行）、**双重防循环**（`stop_hook_active` + 每 session `.done` marker）。
**禁改** settings.json 里除 `hooks` 外的任何键（尤其密钥）；改前先备份。停用 = 删掉 `hooks` 里这两段（或还原备份）。

## 不做

树里不做完整根因分析 / 证据留档 / 恢复步骤（进被链接的 `issue/` 条目或深度文档，模板见 `references/entry-template.md`）；不新建 wiki 引擎；不碰被文档化的源码仓；不跨仓汇总（一仓一档）。
