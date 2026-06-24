# cmdcap — JumpServer 命令/输出捕获工具 设计稿

- 日期: 2026-06-22
- 状态: 待评审 (brainstorming 产出，待用户确认后转 writing-plans)
- 作者: Claude + cuijs

## 1. 背景与目标

在 JumpServer 堡垒机（**在浏览器（Chrome/Edge 等）中打开的 Web 终端 Luna** 接入）后面的目标 Linux 机上排查问题时，Claude Code 驱动整个过程：Claude 给出命令 → 用户在 Luna 里执行 → Claude 需要拿到命令的输出。

> 术语：**Luna** 是 JumpServer 的开源 Web 终端前端（跑在浏览器里的网页 App，用 xterm.js 渲染终端，经 Koko 网关连到目标机），并非浏览器本身。Chrome 只是宿主浏览器。下文"Luna 文件下载(SFTP)"即指 Luna 自带的文件管理功能。

普通 bash 会话默认**只保留命令历史，不保留输出**。本工具的目标：用一条命令把"最近的命令+其输出"存成一份**干净的纯文本**文件，用户通过 Luna 的文件下载（SFTP）拉到本地，Claude 直接读取。

### 成功标准

- 用户在目标机上一条 `cmdcap save` 即可把新产生的命令轮次写成文本文件。
- 文件内容干净（无 ANSI 控制字符、命令与输出配对清晰、带退出码）。
- **增量、不重复**：在 Claude 驱动的逐轮交互中，每次 save 只含上次保存之后的新内容。
- 目标机**零额外运行时依赖**（仅需已有的 bash）。

## 2. 约束（已与用户确认）

1. **接入方式 = Web 终端（Luna）**。用户本地没有该会话的 shell，命令都在远端目标机执行。
2. **取回路径 = 远端先落文件，再由用户用 Luna SFTP 下载到本地**。目标机在堡垒机后面，主动连不到用户的 Windows 机器，没有"直传本地"的通道。代价：每次保存需用户在 Luna 点一次下载。
3. **零额外依赖**：实现为单个 Go **静态二进制**（`linux/amd64`），用户 Luna 上传 + `chmod +x` 即用。不依赖 `script`/`col`/`sed` 等 util-linux 工具。唯一隐性前提：目标机有 `bash`（用其 `PROMPT_COMMAND` 标记命令边界）。
4. **交互是 Claude 驱动、逐轮进行**，因此 `save` 默认**增量**（watermark 游标），避免每次重复拉取旧内容。
5. 目标机架构：`linux/amd64`。命令风格：`cmdcap shell` / `cmdcap save`。

## 3. 总体架构

两半 + 三个动作。

```
[目标机 Luna 终端]                              [Windows 本地]
  cmdcap shell        ← 进会话敲一次，开录制子 shell
     │ (照常敲命令，cd/管道/builtin 都正常)
     ▼
  <Claude 给的诊断命令>
  cmdcap save         ← 把新轮次写成 ~/cmdcap-out/cap-*.txt，打印文件名
     │                         │ Luna 文件下载(SFTP)
     │                         ▼
     │                   D:\wiki\cmdcap-inbox\cap-*.txt
     │                         │ 用户说一声
     ▼                         ▼
  exit (结束录制)        Claude 读最新文件
```

| 动作 | 命令 | 时机 |
|---|---|---|
| 开录 | `cmdcap shell` | 每次进目标机敲一次 |
| 保存增量 | `cmdcap save`（Claude 缀在诊断命令之后单独一行） | 想取回时 |
| 结束 | `exit` | 离开会话 |

## 4. 远端组件：`cmdcap` 二进制（Go）

子命令：`shell` / `save` / `status` / `version`。

### 4.1 会话状态目录

每个录制会话在 `~/.cmdcap/<session-id>/` 下：

| 文件 | 内容 |
|---|---|
| `session.log` | 原始 PTY 输出（typescript，含 ANSI） |
| `index.tsv` | 每条已完成命令一行：`seq \t epoch \t exit \t cwd_b64 \t cmd_b64`（cwd/命令做 base64，避免 tab/换行污染） |
| `cursor` | 已保存到的最大 seq（watermark），初始 0 |
| `marker` | 本会话唯一分隔 token（随机 hex） |
| `seq` | 当前轮次计数器（供 PROMPT_COMMAND 读写） |

`session-id` = `时间戳-pid`。`CMDCAP_SESSION` 环境变量记录当前会话目录，供 `cmdcap save` 定位。

### 4.2 `cmdcap shell`（录制）

1. 生成 session-id、随机 marker，建会话目录。
2. 写一个**临时 rcfile**：
   - `source ~/.bashrc`（若存在），保留用户原有环境/别名。
   - 把 `cmdcap` 二进制所在目录加入 `PATH`（保证子 shell 内 `cmdcap save` 可直接调用，无需用户额外配 PATH）。
   - 安装 `PROMPT_COMMAND` 钩子（见 4.3）。
   - `export CMDCAP_SESSION=<会话目录>`。
3. 用 PTY（`github.com/creack/pty`，纯 Go、`CGO_ENABLED=0` 可静态编译）启动 `bash --rcfile <临时rc> -i`。
4. 桥接 stdin↔pty；pty 输出同时 **写到本地 stdout（用户照常看）** 和 **追加到 `session.log`**。
5. 本地终端置 raw 模式，退出时恢复；监听 `SIGWINCH` 同步窗口大小到 pty。
6. 子 bash `exit` 后，清理临时 rcfile，打印本会话轮次数概要。

### 4.3 PROMPT_COMMAND 钩子（命令边界与索引）

每条命令执行完、下一个提示符出现前触发：

1. 第一行先存 `local ec=$?`（上条命令退出码）。
2. 用 `history 1` 取刚执行的命令原文；与上次记录的 history 编号比较，**编号未前进则跳过**（处理 shell 启动时的首次空触发、重复触发）。
3. **过滤工具自身**：命令匹配 `^cmdcap( |$)` 的不计入轮次（这样 `cmdcap save`/`cmdcap status` 不会变成一轮、也不污染输出）。
4. 否则：递增 `seq`，向 `index.tsv` 追加 `seq \t epoch \t ec \t cwd_b64 \t cmd_b64`，并向终端打印一行分隔标记 `<marker> <seq>`（落入 `session.log`，用于切片输出）。

> 因此 Claude 的发命令约定：**诊断命令各占一行，最后单独一行 `cmdcap save`**。`save` 行被过滤、不计轮次；诊断命令各自成一轮被干净捕获。不要用 `cmd ; cmdcap save` 同行写法（会把两者并成一条 history、污染命令文本与输出）。

### 4.4 输出切片与清洗

`session.log` 中结构：
```
<提示符>$ cmd1（readline 回显）
<cmd1 输出>
<marker 1>          ← PROMPT_COMMAND 在 cmd1 完成后打印
<提示符>$ cmd2
<cmd2 输出>
<marker 2>
...
```
- 第 k 轮输出 = `marker(k-1)`（不含）到 `marker(k)`（不含）之间的文本，去掉**首个物理行**（提示符+命令回显）。k=1 时从日志开头到 `marker 1`。
- 命令原文不从日志解析，直接取 `index.tsv`（准确、无乱码）。
- ANSI 清洗（Go 内实现）：去 CSI `\x1b\[[0-9;?]*[ -/]*[@-~]`、OSC `\x1b\][^\x07]*(\x07|\x1b\\)`；处理 `\r`（回车覆盖，保留行内最终态）、退格。

### 4.5 `cmdcap save [flags]`

定位会话：读 `CMDCAP_SESSION`，缺失则取 `~/.cmdcap/` 下最新会话。

| Flag | 行为 |
|---|---|
| （无） | 取 `cursor+1` 到最新 seq 的所有轮次；保存后 `cursor` 前移到最新。**默认，解决重复问题。** |
| `-n N` | 取最近 N 轮（无视 cursor 选择范围），但保存后仍把 `cursor` 推到最新。 |
| `--from A --to B` | 取指定 seq 区间（用于补取旧内容）；**不**移动 cursor。 |
| `--tail M` | 每轮输出只保留末尾 M 行（大输出安全阀；默认不截断）。 |
| `-o PATH` | 覆盖输出路径。 |

无新轮次时（`cursor` 已是最新且无 `-n/--from`）：提示"无新内容"，不产生空文件。

**输出文件**：`~/cmdcap-out/cap-<epoch>-<fromSeq>-<toSeq>.txt`。格式：
```
# cmdcap dump
host=<hostname> user=<user> session=<id> saved=<本地时间> rounds=<from>-<to>
================================================================
[#5] $ kubectl get pods -n port            (exit=0  cwd=/home/x  2026-06-22 14:03:11)
----------------------------------------------------------------
<清洗后的输出>

================================================================
[#6] $ tail -n 50 /var/log/app.log         (exit=0  cwd=/home/x  2026-06-22 14:03:40)
----------------------------------------------------------------
<清洗后的输出>
```
结尾打印（给用户看）：
```
已保存 2 轮 (#5-#6) → /home/x/cmdcap-out/cap-1750000000-5-6.txt
请用 Luna 下载该文件到 D:\wiki\cmdcap-inbox\
```

### 4.6 `cmdcap status` / `version`

- `status`：打印会话 id、总轮次、cursor、未保存轮次数。
- `version`：版本号 + 构建信息。

## 5. 本地组件（Windows）

纯约定，几乎无代码：

- **收件箱**：`D:\wiki\cmdcap-inbox\`。用户 Luna 下载到此目录。Claude 按修改时间读**最新**文件（注意本机递归 Glob 失效，用 `find`/按目录列）。
- **源码与产物**：`D:\jk_file\skills\cmdcap\`（Go 源码）、`D:\jk_file\skills\cmdcap\dist\cmdcap-linux-amd64`（编好的二进制）、`D:\jk_file\skills\cmdcap\README.md`（安装/用法）。

## 6. 安装与交付

- **构建**（本机交叉编译）：`CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -ldflags "-s -w" -o dist/cmdcap-linux-amd64 ./cmd/cmdcap`。前置：本机需有 Go 工具链；实现计划第一步先确认，没有则给用户源码 + 构建命令。
- **目标机安装**（一次性）：Luna SFTP 上传 `cmdcap-linux-amd64` 到 `~/`，`mv ~/cmdcap-linux-amd64 ~/cmdcap && chmod +x ~/cmdcap`。调用 `~/cmdcap shell`（或将 `~` 加入 PATH 后直接 `cmdcap`）。
- **每次会话**：`~/cmdcap shell`（之后子 shell 内 `cmdcap save` 已在 PATH，可直接用）。

## 7. 已知边界（写入 README）

- 面向**行式诊断命令**（ps / cat / tail / curl / kubectl get / 看日志等）。`vim`/`top`/交互式 `less` 等全屏 TUI 会刷屏，去 ANSI 后仍乱——不适合用本工具捕获。
- `save` **不重跑命令、无副作用**（这是选本方案而非"重跑历史"方案的核心原因）。
- 每次保存需用户在 Luna 手动下载一次（堡垒机隔离的固有代价）。
- 需目标机有 `bash`；若默认 shell 为 `sh/dash`（无 `PROMPT_COMMAND`），`cmdcap shell` 强制用 `bash`（存在则用，否则报错提示）。
- 未先 `cmdcap shell` 就 `cmdcap save`：报错并给出指引。
- 极长换行命令的输出切片首行启发式可能有小偏差（命令原文取自 index，不受影响）。
- 分隔标记为明文打印（求切片可靠），用户实时终端里每条命令后会多一行标记噪声。可接受；后续可选用非打印的 OSC 转义隐藏（需确认 Luna xterm.js 不会显示乱码）。

## 8. 不做（YAGNI）

- 不做"目标机自动推送到本地"（隔离约束，做不到）。
- 不做把 SFTP 挂成本地盘的自动同步（可选优化，先不做）。
- 不接 JumpServer 的会话录像 / 命令审计 API（需管理员权限、回放是 asciinema 需转换、链路重）。
- 不做方案 B（重跑最近 N 条命令）——有副作用风险，已弃。

## 9. 实现拆分（交给 writing-plans 细化）

1. 确认本机 Go 工具链；建 `D:\jk_file\skills\cmdcap\` 骨架（go.mod、cmd/cmdcap）。
2. `cmdcap shell`：PTY 录制 + 临时 rcfile + PROMPT_COMMAND 钩子 + 索引写入。
3. ANSI 清洗 + 输出切片模块（可单测）。
4. `cmdcap save`：游标/增量、flags、文件格式。
5. `status`/`version`、错误指引、PATH 注入。
6. 交叉编译产物 + README（安装、用法、边界）。
7. 端到端验证（在一台可达 Linux 上跑一遍 shell→若干命令→save→检查文件）。
