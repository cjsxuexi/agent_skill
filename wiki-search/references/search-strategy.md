# Wiki 检索策略

本文是 wiki 检索的操作手册：先解析路径占位符（§1），再按场景选路径——故障定位先查诊断树（§2），普通任务走分层 grep（§3）；按任务类型直达目标节（§4）；三类可复制命令（§5）与收窄技巧（§6）。全程只读：绝不修改 wiki 下任何文件。

## 1. 占位符与解析方法

本文所有命令用占位符书写，替换为本机解析值即可运行。

| 占位符 | 含义 | 解析方法 |
|---|---|---|
| `<WIKI_BASE>` | wiki 根目录 | 用户主目录 `~/.document-systems.json` 的 `wiki_base` 字段（§1.1） |
| `<REPO_ROOT>` | 目标源码仓的本机根目录 | 由任务上下文给出（当前工作目录或用户指明的仓路径） |
| `<仓名>` | 仓库名 | `<REPO_ROOT>` 最后一级目录名 |
| `<DOMAIN>` | 仓所属业务域 | wiki_engine `resolve-domain` 解析（§1.3） |
| `<DOC_ROOT>` | 该仓的文档根目录 | `<WIKI_BASE>\<DOMAIN>\<仓名>` |
| `<ENGINE_CLI>` | wiki_engine 命令行入口 | document-systems skill 安装目录下的 `scripts\wiki_engine\cli.py`（§1.2） |
| `<子系统>` | 仓内子系统目录名 | `<DOC_ROOT>` 下一级子目录，每个含一份 `architecture.md` |
| `<检索根>` | 分层检索的根目录 | 按 §3 取 `<DOC_ROOT>` / `<WIKI_BASE>\<DOMAIN>` / `<WIKI_BASE>` |
| `<关键词>`、`<N>` | 检索词 / 目标节号 | 由任务拆解得出；`<N>` 的取值见 §4 映射表 |

### 1.1 解析 WIKI_BASE

PowerShell：

```powershell
(Get-Content "$env:USERPROFILE\.document-systems.json" -Encoding UTF8 | ConvertFrom-Json).wiki_base
```

Git Bash：

```bash
python -X utf8 -c "import json,os;print(json.load(open(os.path.expanduser('~/.document-systems.json'),encoding='utf-8'))['wiki_base'])"
```

### 1.2 定位 ENGINE_CLI

`<ENGINE_CLI>` 位于已安装的 document-systems skill 目录内，相对该 skill 根目录的路径固定：

```text
<document-systems 安装目录>\scripts\wiki_engine\cli.py
```

skill 安装根目录随环境不同：用户级安装在 `~\.claude\skills\`（PowerShell 写 `$env:USERPROFILE\.claude\skills\`），项目级安装在项目的 `.claude\skills\`。按「项目级 → 用户级」顺序探测，取第一个存在者，例如：

```powershell
Get-Item "$env:USERPROFILE\.claude\skills\document-systems\scripts\wiki_engine\cli.py"
```

### 1.3 解析 DOMAIN → 拼出 DOC_ROOT

```powershell
python -X utf8 <ENGINE_CLI> resolve-domain --repo <REPO_ROOT> --wiki <WIKI_BASE>
```

命令输出单个 JSON 对象，取其 `domain` 字段。示例输出（本机示例值，实际以解析结果为准）：

```json
{"status": "resolved", "repo": "fms-server", "domain": "NP_FMS", "source": "parent"}
```

于是 `<DOC_ROOT> = <WIKI_BASE>\<DOMAIN>\<仓名>`（示例值：`wiki_base` 为 `D:\wiki`、仓为 `fms-server` 时，DOC_ROOT 即 `D:\wiki\NP_FMS\fms-server`）。

不带 `--set` 的 `resolve-domain` 是纯只读解析，不写任何文件，符合本 skill 只读约束；**不要**使用 `--set`（它会改写域白名单，属维护侧操作）。`status` 非 `resolved`（如 `no_registry`）或退出码非 0（如父目录不在域白名单的报错）时：不要猜 DOMAIN，改用 §3 第二/三层的更大检索根直接做关键词检索，或请用户指明目标域。

### 1.4 文档布局速览

- `<DOC_ROOT>\architecture.md` — 仓级总览；
- `<DOC_ROOT>\<子系统>\architecture.md` — 子系统文档，正文遵循 §1–§10 固定结构（§1 概述 / §2 入口 / §3 目录结构 / §4 对外接口 / §5 依赖 / §6 关键流程 / §7 数据模型 / §8 关键配置 / §9 已知问题 / §10 待确认）；
- `<DOC_ROOT>\生产问题速查.md` — 故障诊断树（现象 → 根因），仅部分仓已建立。

各仓的节标题措辞可能略有差异（如 §5 或作「上下游依赖」、§7 或作「数据资产」），**定位节一律按节号 `^## N\.` 匹配，勿按节名全字匹配**。

## 2. 故障定位场景：先查诊断树，再查架构文档

任务是故障排查、现象定位、「为什么 X 不工作」时，按本节顺序执行：诊断树 → 架构文档。其余任务直接走 §3。

### 2.1 读取诊断树

PowerShell：

```powershell
Get-Content "<DOC_ROOT>\生产问题速查.md" -Encoding UTF8
```

Git Bash（`<DOC_ROOT>` 用正斜杠形式，如 `D:/wiki/...`，示例值）：

```bash
cat "<DOC_ROOT>/生产问题速查.md"
```

文件不存在 = 该仓尚未建立速查：在结论中注明「该仓暂无生产问题速查」，直接转 §3 分层检索。

### 2.2 树的用法：现象根 → 判别 → 根因叶

树的固定结构：每个 `##` 标题是一个**现象根**（用户可感知的故障现象）；其下并列若干「**判别**」分支（可观测证据，用于区分同一现象的不同成因）；每条判别分支收敛到一个「**根因**」叶子（候选根因 + 「确认 →」指向的架构文档锚点或专项排查文档）。

1. **对现象**：把用户报告的现象对照全部现象根，选最匹配的一个。可先只列现象根清单：

   ```powershell
   Get-Content "<DOC_ROOT>\生产问题速查.md" -Encoding UTF8 | Select-String -Pattern "^## "
   ```

   ```bash
   grep -n "^## " "<DOC_ROOT>/生产问题速查.md"
   ```

2. **走判别**：沿该现象根下的判别分支，逐条对照手头证据（报错类型、日志关键字、监控表现），排除不符的分支，收窄到一条。判别项本身就是取证清单——缺哪条证据就先补哪条。
3. **取根因**：读该分支的根因叶子，得到候选根因与「确认 →」锚点；沿锚点到对应架构文档节核实。速查命中 ≠ 定案，仍需按锚点与运行时证据确认。

### 2.3 命中 / 未命中的处理

- **命中**：直接引用速查**原文片段**并标注来源，格式：「在 `<DOC_ROOT>\生产问题速查.md`「<现象根标题>」中找到：<原文片段>」。只贴原文，不转述、不改写。
- **未命中**：如实注明「**速查暂无此现象**」，转 §3 分层检索补充上下文；此时优先读 §9 已知问题、§6 关键流程（见 §4 映射表「排查已知问题」行）。

## 3. 普通任务场景：分层 grep（仓 → 域 → 全 wiki）

三层共用同一命令形状（§5.1），只换检索根；**上一层无结果才升层**，有结果就地收窄（§6），不要越层撒网：

| 层 | 检索根 | 升层条件 |
|---|---|---|
| 第一层（仓级，精准） | `<DOC_ROOT>` | ——（默认起点） |
| 第二层（域级，扩大） | `<WIKI_BASE>\<DOMAIN>` | 第一层 0 命中（关键词的中英文、缩写等变体都试过）才升层 |
| 第三层（全 wiki，兜底） | `<WIKI_BASE>` | 第二层仍 0 命中，或无法确定 DOMAIN |

命中后的引用格式统一为：「在 `<文件路径>` §N 中找到：<原文片段>」——直接引用原文，不转述。

## 4. 任务类型 → 目标节映射表

定向读节前先对任务分型，确定 `<N>`；「优先 §节」无收获再读「次要 §节」。定向命令见 §5.2 / §5.3。

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

## 5. 三类可复制命令（PowerShell / Git Bash 双版）

约定：PowerShell 读文件一律带 `-Encoding UTF8`；Git Bash 中路径用正斜杠形式（如 `D:/wiki/...` 或 `/d/wiki/...`，示例值）。

### 5.1 宽检索：关键词扫 wiki 树内全部知识 md（排除噪声）

`<检索根>` 取 §3 对应层的根目录。扫描对象是 wiki 树内全部 `*.md` 知识文档——除 `architecture.md` 外，还包括自定义名知识文档（如 `alarm-architecture.md`、`business-reporting-overview.md`、`runbook-vehicle-location-ws.md`）、`whole_architecture.md` 仓级总览、`issue\**` 排障笔记、`_common\*.md` 术语表、`生产问题速查.md`；同时按路径规则排除四类噪声：① `.` 开头的文件/目录（`.review.md`、`.analysis.md`、`.claude\`）、② `spec\` 需求实现工作区、③ `_common` 以外的 `_*` 目录（如 `_meta\`）、④ `index.md` 域级导航页。

```powershell
Get-ChildItem "<检索根>" -Recurse -Filter *.md |
  Where-Object { $_.FullName -notmatch '\\\.|\\spec\\|\\_(?!common\\)|\\index\.md$' } |
  Select-String -Pattern "<关键词>" -Encoding UTF8
```

```bash
grep -rn --include='*.md' --exclude='.*' --exclude='index.md' \
  --exclude-dir='.*' --exclude-dir='spec' --exclude-dir='_meta' \
  "<关键词>" "<检索根>"
```

两版语义一致（已对全 wiki 核对选中文件集合相同）。差异：Git Bash 版的 `_*` 目录排除是逐个枚举的（当前只有 `_meta`），wiki 树新增 `_common` 以外的 `_*` 目录时需同步补 `--exclude-dir`；PowerShell 版的 `\\_(?!common\\)` 自动覆盖，无需维护。

### 5.2 节定向：定位 `^## N.` 起始行并取后续若干行

```powershell
Get-Content "<DOC_ROOT>\<子系统>\architecture.md" -Encoding UTF8 |
  Select-String -Pattern "^## <N>\." -Context 0,50
```

```bash
grep -n -A 50 "^## <N>\." "<DOC_ROOT>/<子系统>/architecture.md"
```

`50` 为向后取的行数，按节长调整。要整节取全（至下一节标题为止），Git Bash 可用：

```bash
sed -n '/^## <N>\./,/^## [0-9]/p' "<DOC_ROOT>/<子系统>/architecture.md"
```

### 5.3 关键词限范围：限某子系统 / 限某节

**限某子系统**（单文件内检索）：

```powershell
Select-String -Pattern "<关键词>" -Path "<DOC_ROOT>\<子系统>\architecture.md" -Encoding UTF8
```

```bash
grep -n "<关键词>" "<DOC_ROOT>/<子系统>/architecture.md"
```

**限某节**（先框定节的行区间，再在区间内匹配；`<M>` = 下一节的节号，通常为 N+1）：

```powershell
$lines = Get-Content "<DOC_ROOT>\<子系统>\architecture.md" -Encoding UTF8
$s = ($lines | Select-String '^## <N>\.' | Select-Object -First 1).LineNumber
$e = ($lines | Select-String '^## <M>\.' | Select-Object -First 1).LineNumber
if (-not $e) { $e = $lines.Count + 1 }   # <N> 为最后一节时取到文件末尾
$lines[($s-1)..($e-2)] | Select-String '<关键词>'
```

```bash
sed -n '/^## <N>\./,/^## [0-9]/p' "<DOC_ROOT>/<子系统>/architecture.md" | grep -n "<关键词>"
```

## 6. 结果太多时如何收窄

按代价从低到高依次尝试：

1. **叠加关键词（AND）**：两个关键词同行才保留。

   ```powershell
   Get-ChildItem "<检索根>" -Recurse -Filter *.md |
     Where-Object { $_.FullName -notmatch '\\\.|\\spec\\|\\_(?!common\\)|\\index\.md$' } |
     Select-String -Pattern "<关键词1>" -Encoding UTF8 |
     Where-Object { $_.Line -match "<关键词2>" }
   ```

   ```bash
   grep -rn --include='*.md' --exclude='.*' --exclude='index.md' \
     --exclude-dir='.*' --exclude-dir='spec' --exclude-dir='_meta' \
     "<关键词1>" "<检索根>" | grep "<关键词2>"
   ```

2. **按任务类型直达目标节**：对照 §4 映射表确定 `<N>`，改用 §5.3「限某节」检索，只在目标节内匹配关键词。
3. **先节定向再全文**：把「全文关键词匹配」降级为「先读目标节（§5.2）、节内没有答案再放开到整个文件」——多数任务的答案就在映射表指到的节里。
4. **按子系统缩小范围**：宽检索命中散布在多个子系统时，先读 `<DOC_ROOT>\architecture.md`（仓级总览）判断哪个子系统才是任务主体，再把检索限到该子系统（§5.3）。
5. **截断预览**：初查只看前若干条确认方向，再放开（PowerShell 追加 `| Select-Object -First 20`，Git Bash 追加 `| head -20`）。
