# 排查工具调用指引

本文是「排查工具证据收集」阶段（Phase 3）的操作参考。wiki 提供设计意图（应然），排查工具提供运行时实况（实然），两类信息互为补充、缺一不可。本文覆盖六个工具：工具选择矩阵（§1）、fms-diagnose（§2）、fms-log（§3）、cmdcap（§4）、gitnexus 系列（§5），并以一个端到端场景收尾（§6）。全部工具**只读取证**，不改变目标系统与代码仓的任何状态。

## 1. 工具选择矩阵

| 任务类型 | 适用工具 | 一句话用法 |
|---|---|---|
| FMS 业务故障诊断（车辆离线 / 任务分配失败 / 任务卡住 / 告警不消 / Solace·TOS 作业进不来 / 路径规划失败 / DB·Redis 异常） | fms-diagnose | 先 `--list` 选检查项，再 `--port <港口> --check <检查名>`（§2） |
| 查错误日志 / 报文 / 异常堆栈，接口 500 或慢 | fms-log | 按港口选日志源，先 `--list` 再 tail/grep（§3） |
| 只能经堡垒机（JumpServer Luna 终端）到达的目标机上执行命令取证 | cmdcap | `cmdcap shell` → 逐行命令 → `cmdcap save` 单独一行（§4） |
| 代码调用链追踪、错误来源定位 | gitnexus-debugging | `gitnexus_query` → `gitnexus_context` → 读 process 资源（§5） |
| 陌生模块结构、执行流理解 | gitnexus-exploring | 读仓 context 资源 → `gitnexus_query` → `gitnexus_context`（§5） |
| 改动影响面评估 | gitnexus-impact-analysis | `gitnexus_impact({target, direction: "upstream"})`（§5） |

选型原则：

- **非互斥，可并用**。一次故障排查常见组合：fms-log 锚定现象 → gitnexus-debugging 定位代码 → fms-diagnose 补系统横断面（见 §6）。
- **全部只读**。六个工具都只 SELECT / SCAN / 查日志 / 查代码索引，取证过程不写库、不改缓存、不动代码；凭证不写入 wiki、Agent 对话或日志，命令示例只记录入口与参数形状。
- **优先触发对应 skill**。六个工具均为已安装 skill：触发后完整说明（环境差异、凭据位置、最新注意事项）会进入上下文。本文是选型与核心语法速查，更深的领域细节以各 skill 自带文档为准。

### 1.1 命令中的路径占位符

本文命令用 `<SKILLS_ROOT>` 指代 skill 安装根目录：项目级在项目的 `.claude\skills\`，用户级在 `~\.claude\skills\`（PowerShell 写 `$env:USERPROFILE\.claude\skills\`），按「项目级 → 用户级」顺序探测，取第一个存在者。

fms-diagnose / fms-log 的安装目录可能是指向工作副本的目录链接（junction）；脚本按自身真实位置解析内部连接配置，**直接用 `<SKILLS_ROOT>` 下的路径调用即可**，无需关心底层配置文件在哪。

## 2. fms-diagnose — FMS 业务故障自动诊断

### 2.1 适用场景与港口差异

诊断 FMS（港口无人集卡 / IGV 车队管理系统）的业务故障，自动从 MySQL/Oracle + Redis + Loki 三路取证，输出结构化结论。两个港口结构不同，直接决定检查项的可用范围：

| | NP | PSA |
|---|---|---|
| 数据库 | MySQL（库 `fms`） | Oracle（schema `C##FMS1`） |
| 作业来源 | bridge-gRPC + TOS REST 注入 | Solace HTMS（GTOS+） |
| 核心模块 | fms-vehicle-bridge | fms-jobflow（Solace 全在这） |
| 服务日志 | k8s（不在 Grafana，用 fms-log `--port np` 查） | Grafana/Loki |

> 直接后果：`psa-solace-intake` 及所有 Loki 日志类检查（`psa-routing-logs` / `psa-service-health` / `psa-log-search`）只对 PSA 有效；NP 的日志证据走 fms-log 的 k8s 路径（§3）。

### 2.2 工作流：先 `--list`，再 `--check`

**第一步**：列出可用检查项（`--list` 不需要 `--port`）：

```powershell
python -X utf8 "<SKILLS_ROOT>\fms-diagnose\scripts\fms_diagnose.py" --list
```

输出按 scope 分三组：`common`（两港口通用）、`np-*`（仅 NP）、`psa-*`（仅 PSA）。`--port` 取值 `np` / `np_prod` / `psa` / `psa_prod`：np 系跑 common + np-\*，psa 系跑 common + psa-\*，跨港口调用会明确报错。

**第二步**：按现象选 check 执行（示例见 §2.4）。可选参数：`--minutes`（回溯窗口）、`--limit`（行数上限）；`psa-log-search` 专用 `--app`（模块）与 `--grep`（过滤）。

### 2.3 现象 → 检查项速查

检查项清单以 `--list` 实时输出为准，常用对照：

| 现象 | 优先检查项（scope） |
|---|---|
| 车辆离线 / 不动 | `vehicle-online`、`vehicle-status`（common）；NP 加查 `np-bridge-health`、`np-stream-backlog` |
| 任务分配不出去 / 卡住 | `job-task-overview`、`task-stuck`（common） |
| 告警不消 / 告警风暴 | `alarm-active`、`alarm-recent`（common） |
| 路径规划失败 / 改派异常 | `routing-status`（common）；PSA 加查 `psa-routing-logs` |
| PSA 作业进不来 | `psa-solace-intake`（psa） |
| DB 异常 / 接口慢 | `db-health`、`db-slow-queries`（common） |
| Redis 异常 / 消费停滞 | `redis-overview`（common）；NP 加查 `np-stream-backlog` |
| 某模块错误率高 / 崩溃（PSA） | `psa-service-health`；自由文本查日志用 `psa-log-search` |

### 2.4 命令示例

```powershell
# 车辆在线情况（common 检查，两港口都能跑）
python -X utf8 "<SKILLS_ROOT>\fms-diagnose\scripts\fms_diagnose.py" --port np --check vehicle-online

# PSA 作业进料诊断（psa 专属）
python -X utf8 "<SKILLS_ROOT>\fms-diagnose\scripts\fms_diagnose.py" --port psa --check psa-solace-intake

# PSA 自由文本查某模块日志（psa-log-search 支持 --app / --grep）
python -X utf8 "<SKILLS_ROOT>\fms-diagnose\scripts\fms_diagnose.py" --port psa --check psa-log-search --app fms-jobflow --grep "No handler found"
```

### 2.5 输出字段解读

每个检查输出四个字段：

| 字段 | 含义 | 用法 |
|---|---|---|
| `status` | 结论级别：`ok` / `info` / `warn` / `alert` / `error` | `alert`/`error` 是强信号，优先追；`warn` 需结合其他证据判断 |
| `headline` | 一句话结论 | 可直接作为「实然」证据引用 |
| `evidence` | 取证明细（SQL 结果 / Redis 值 / 日志行） | 引用时保留关键行，注明来源 |
| `suggestions` | 下一步排查建议 | 作为后续取证方向，不等于结论 |

引用诊断结果时注明来源与参数，如：【来源：fms-diagnose `--port np --check vehicle-online`】。

### 2.6 走更深

诊断收敛到某辆车 / 某个任务后，用 fms-diagnose skill 自带的参考继续手查：`references/fms-domain.md`（表结构、Redis key 目录、失败日志签名、各模块职责）、`references/diagnostics.md`（每个检查项的排查套路）。

## 3. fms-log — 按港口查 FMS 服务日志

### 3.1 港口 → 日志源对应关系

统一入口 `fms_log.py --port <PORT>`，`--port` 必填，取值与日志源：

| `--port` | 环境 | 日志源 |
|---|---|---|
| `np` | NP 测试 | k8s：模块 pod 内 `/logs` 文件；另可加 `--loki` 查推送到 Loki 的历史日志 |
| `np_prod` | NP 生产 | k8s：模块 pod 内 `/logs` 文件（不支持 `--loki`） |
| `dg` | DG 测试 | raw Loki：同 NP Loki endpoint，namespace=`dg-fms`（仅支持 `--loki`） |
| `psa` | PSA 测试 | Grafana/Loki |
| `psa_prod` | PSA 生产 | Grafana/Loki |
| `nb` | NB 测试 | 直连 SSH 读云控 VM 上的日志文件 |
| `nb_uat` | NB UAT | 直连 SSH（uat 目录） |
| `yz` | 甬舟测试 | Grafana/Loki（app 为 port-\*） |

> 注意与 fms-diagnose 区分：fms-diagnose 的 `--port` 只有 4 个取值（np/np_prod/psa/psa_prod），fms-log 有上表 8 个。个别环境的临时可用性问题（如某生产 Loki 后端故障）以 fms-log skill 文档的最新注意事项为准。

### 3.2 关键参数

| 参数 | 含义 |
|---|---|
| `--module` / `--app` | 模块名（两者互为别名：NP=Deployment 名，PSA=Loki app，NB=云控模块目录）。常见值：`fms-gateway` `fms-system` `fms-vehicle-bridge` `fms-jobflow` `fms-routing` `fms-hdmap` `fms-diagnostic` `fms-recorder` `fms-edge-receiver` `routing-service` |
| `--list` | NP/NB：列日志文件；PSA/yz：列活跃 app |
| `--grep` | 过滤。**语义分港口：NP/NB 是 `grep -E` 正则；PSA 与 `--loki` 是子串匹配（非正则）** |
| `--file` | NP/NB：日志文件名，默认 `service.log`（用 `--list` 查可用文件） |
| `--relpath` | 仅 NB：以相对路径直接指定日志文件（替代 `--module`） |
| `--lines` | 返回行数，默认 200 |
| `--minutes` | 回溯分钟数，默认 10（PSA 与 `--loki` 生效；NP 文件模式忽略） |
| `--ignore-case` | NP/NB grep 忽略大小写 |
| `--context` | NP/NB grep 上下文行数（`grep -C`） |
| `--pod-logs` | NP：改用 `kubectl logs` 取实时 stdout（而非读 `/logs` 文件） |
| `--previous` | NP 配合 `--pod-logs`：取 crash 前的容器 stdout |
| `--loki` | `--port np` / `--port dg`：查推送到 raw Loki 的日志（历史 / 跨副本 / 按时间范围） |

### 3.3 工作流：先 `--list`，再实际查

先 `--list` 确认目标（NP/NB 看有哪些日志文件、NB 看真实目录布局、PSA/yz 看活跃 app 名），再 tail/grep，避免对着猜出来的模块名或文件名空查。

### 3.4 命令示例

```powershell
# NP：先看模块有哪些日志文件，再 tail
python -X utf8 "<SKILLS_ROOT>\fms-log\scripts\fms_log.py" --port np --module fms-system --list
python -X utf8 "<SKILLS_ROOT>\fms-log\scripts\fms_log.py" --port np --module fms-system --lines 200

# NP：正则抓错误 + 上下文（NP 的 --grep 是 grep -E 正则）
python -X utf8 "<SKILLS_ROOT>\fms-log\scripts\fms_log.py" --port np_prod --module fms-gateway --grep "ERROR|Exception" --ignore-case --context 2

# NP：kubectl logs 实时 stdout；--previous 看 crash 前
python -X utf8 "<SKILLS_ROOT>\fms-log\scripts\fms_log.py" --port np_prod --module fms-vehicle-bridge --pod-logs --lines 100

# NP（仅测试）：查 Loki 历史日志（--grep 为子串）
python -X utf8 "<SKILLS_ROOT>\fms-log\scripts\fms_log.py" --port np --loki --module fms-system --grep "ERROR" --minutes 60

# DG：同 NP raw Loki endpoint，namespace=dg-fms；先列 app，再查模块
python -X utf8 "<SKILLS_ROOT>\fms-log\scripts\fms_log.py" --port dg --loki --list --minutes 60
python -X utf8 "<SKILLS_ROOT>\fms-log\scripts\fms_log.py" --port dg --loki --app fms-vehicle-bridge --minutes 30 --lines 200

# PSA：按 app 查 Loki（--grep 为子串），可回溯分钟
python -X utf8 "<SKILLS_ROOT>\fms-log\scripts\fms_log.py" --port psa --app fms-jobflow --grep "No handler found" --minutes 30

# NB：先 --list 看真实布局，再按模块或相对路径查
python -X utf8 "<SKILLS_ROOT>\fms-log\scripts\fms_log.py" --port nb --list
python -X utf8 "<SKILLS_ROOT>\fms-log\scripts\fms_log.py" --port nb_uat --relpath logs/port-device/error.log --grep "Exception" --context 2
```

引用日志证据时注明来源与参数，如：【来源：fms-log `--port np --module fms-gateway --grep "ERROR|Exception"`】。

## 4. cmdcap — 堡垒机后目标机的命令输出捕获

### 4.1 适用场景

仅当同时满足：① 目标 Linux 机只能经 JumpServer 堡垒机的 Luna web 终端到达；② 无法 SSH 直连、目标机也无法反向连到本机；③ 需要把诊断命令的输出以文件形式取回分析（尤其是大段或多命令输出）。

若日志能由 fms-log 直接查到（§3），优先 fms-log，不必动用 cmdcap。

### 4.2 标准序列（在 Luna 终端内按序执行）

1. `cmdcap shell` — 每会话执行一次，进入录制子 shell（首次使用的新目标机需先安装：把 cmdcap skill 目录 `dist\` 下的预编译二进制上传到目标机，步骤见 cmdcap skill 文档；已配置过的主机用下表固定启动路径）。
2. 正常执行诊断命令，**每条命令独立一行**。
3. `cmdcap save` — **单独一行**，把本批新输出刷到文件并打印文件路径。
4. 用户经 Luna 文件管理器把该文件下载到本机 `~\Downloads\`。
5. 读取最新一份捕获文件：

```powershell
Get-ChildItem "$env:USERPROFILE\Downloads\cap-*.txt" | Sort-Object LastWriteTime | Select-Object -Last 1 | Get-Content -Encoding UTF8
```

6. 全部取证结束后在录制 shell 内 `exit` 结束录制。

已知目标机的启动路径只记录命令入口，不记录凭证：

| Host (prompt) | Step 1 launch command |
|---|---|
| `fabu@fabubak02` | `~/nb_port_prodprev/scripts/cmdcap shell` |
| `fabu@fabu02` | `~/tools/cmdcap shell` |

若不确定当前 Luna 终端是哪台主机，先看 shell prompt；仍不确定时同时给两条候选启动命令，让人工按 prompt 选择。

### 4.3 硬性规则

- **禁止把 cmdcap 与其他命令用 `;` 拼在一行**。cmdcap 按「一行 = 一轮」切分输出，拼接既污染该轮记录、`save` 也不会被识别：

  ```text
  ✅ 正确                                ❌ 错误
  kubectl get pods -n port               kubectl get pods -n port ; cmdcap save
  systemctl status docker
  cmdcap save
  ```

- `cmdcap save` **不带任何命令参数**——它是刷出动作，不是命令包装器（❌ `cmdcap save df -h`）。
- `save` 在录制 shell **内**执行，不能放在 `exit` 之后。
- `save` 是**增量**的：每次只返回上次 save 之后的新轮次；要重取旧轮次用 `--from/--to`。
- cmdcap 只作为 fms-log / fms-diagnose 覆盖不到时的兜底取证入口；不要把 Nacos/JumpServer 查询能力重复沉淀成本人脚本，也不要把账号、token、密钥、内网凭据写进命令、wiki、日志或 Agent 对话。

### 4.4 save 选项与边界

| 命令 | 用途 |
|---|---|
| `cmdcap save` | 刷出上次 save 以来的新轮次（默认，增量） |
| `cmdcap save -n 3` | 只取最近 3 轮 |
| `cmdcap save --from 5 --to 7` | 重取指定轮次范围（不移动增量游标） |
| `cmdcap save --tail 100` | 每轮只保留最后 100 行输出 |
| `cmdcap status` | 查看会话 id、轮次数、游标位置 |

边界：只适合行输出命令；`vim` / `top` / 交互式 `less` 等全屏 TUI 会录成乱码，不要在录制中运行。

## 5. gitnexus-* — 代码调用链、模块结构与改动影响面

### 5.1 三个 skill 的分工

| skill | 用途 | 典型问题 |
|---|---|---|
| gitnexus-debugging | 调用链追踪、错误来源定位 | 「这个接口为什么 500」「错误从哪里抛出」「谁调用了这个方法」 |
| gitnexus-exploring | 陌生模块结构、执行流理解 | 「X 功能是怎么实现的」「这个模块的入口在哪」 |
| gitnexus-impact-analysis | 改动影响面评估 | 「改了 X 会影响谁」「这样改安全吗」——结果直接作为风险清单「依赖风险」方向的输入（见 risk-checklist.md） |

### 5.2 前提：目标仓已建索引（未建则先兜底）

gitnexus 查询基于预建代码索引。**目标仓未 index、或查询返回「Index is stale」时，先在仓根目录（必须在 git 仓内）运行 analyze 再查询**：

```powershell
npx gitnexus status    # 查看当前仓有无索引、是否过期
npx gitnexus analyze   # 建立 / 刷新索引
```

### 5.3 核心查询

调用链追踪（gitnexus-debugging 工作流）：

```text
1. gitnexus_query({query: "<错误现象 / 接口路径 / 概念>"})   → 找到相关执行流(process)与符号
2. gitnexus_context({name: "<嫌疑函数或类>"})                → 该符号的调用方 / 被调方 / 所属流程
3. READ gitnexus://repo/<仓名>/process/<流程名>              → 逐步执行链，顺链定位
4. gitnexus_cypher({query: "MATCH ..."})                     → 需要自定义图查询时使用
```

模块结构理解（gitnexus-exploring 补充资源）：

```text
READ gitnexus://repos                        → 已建索引的仓列表
READ gitnexus://repo/<仓名>/context           → 仓概览 + 索引新鲜度
READ gitnexus://repo/<仓名>/clusters          → 功能分区一览
READ gitnexus://repo/<仓名>/cluster/<分区名>  → 分区成员与文件路径
```

改动影响面（gitnexus-impact-analysis）：

```text
gitnexus_impact({target: "<符号名>", direction: "upstream", minConfidence: 0.8, maxDepth: 3})
  → 按深度分层返回依赖方：
     d=1 直接调用方（改动后必然受影响）
     d=2 间接依赖（大概率受影响）
     d=3 传递影响（需要测试确认）

gitnexus_detect_changes({scope: "staged"})
  → 把当前 git 改动映射到受影响的执行流（提交前自查）
```

### 5.4 与风险清单联动

评估改动时，把 `gitnexus_impact` 的 d=1 / d=2 清单和受影响执行流数量，作为「依赖风险」高 / 中 / 低判定的直接证据（判定标准见 risk-checklist.md）；受影响面大或落在关键路径上时，把清单原样列入风险条目。

## 6. 场景示例：fms-gateway 接口 500

任务：NP 环境 fms-gateway 某接口返回 500，定位根因。（本节以 NP 测试环境为例，`--port` 按实际环境替换；引用的输出内容均为演示用示例值。）

工具顺序：**fms-log 锚定现象 → gitnexus-debugging 定位代码 → 按需 fms-diagnose 补系统面 → 极少数情况 cmdcap 兜底**。

**第 1 步 — fms-log 查 gateway 错误日志**（拿到异常堆栈、出错接口路径、时间点）：

```powershell
# 先确认该模块有哪些日志文件
python -X utf8 "<SKILLS_ROOT>\fms-log\scripts\fms_log.py" --port np --module fms-gateway --list

# 抓错误与异常堆栈（NP 的 --grep 是 grep -E 正则）
python -X utf8 "<SKILLS_ROOT>\fms-log\scripts\fms_log.py" --port np --module fms-gateway --grep "ERROR|Exception" --ignore-case --context 3

# 若怀疑刚发生过崩溃 / 重启：取 crash 前的容器 stdout
python -X utf8 "<SKILLS_ROOT>\fms-log\scripts\fms_log.py" --port np --module fms-gateway --pod-logs --previous --lines 100
```

产出示例（演示值）：`NullPointerException at JobOrderController.query(...)`，发生于某接口调用时刻。

**第 2 步 — gitnexus-debugging 追调用链**（用第 1 步拿到的类 / 方法 / 接口路径作为查询词；目标仓未建索引则先按 §5.2 运行 `npx gitnexus analyze`）：

```text
gitnexus_query({query: "JobOrderController query"})
gitnexus_context({name: "query"})
READ gitnexus://repo/<仓名>/process/<相关流程名>
```

产出：从抛错点沿调用链收敛到具体文件 / 方法的根因候选（如上游传参为空、外部调用无超时等）。

**第 3 步 — 按需 fms-diagnose 补系统横断面证据**（当日志指向环境或数据问题时）：

```powershell
# 堆栈指向 DB 超时 / 慢查询时
python -X utf8 "<SKILLS_ROOT>\fms-diagnose\scripts\fms_diagnose.py" --port np --check db-health
python -X utf8 "<SKILLS_ROOT>\fms-diagnose\scripts\fms_diagnose.py" --port np --check db-slow-queries

# 现象伴随作业 / 任务数据异常时
python -X utf8 "<SKILLS_ROOT>\fms-diagnose\scripts\fms_diagnose.py" --port np --check job-task-overview
```

PSA 版差异：日志改用 `--port psa --app fms-gateway`（Loki，`--grep` 为子串）；系统面可加 `psa-service-health`（各模块错误率 + 崩溃样本）与 `psa-log-search`。

**第 4 步 —（兜底，通常不需要）**：若必须到堡垒机后的节点上执行命令（如 `kubectl describe`、网络诊断）且无法直连，按 §4 的序列用 cmdcap 取回输出。

结束前自查：日志证据（实然）与代码链路（应然）是否互相印证收敛到唯一根源；若仍存在两个以上互斥候选，回到 §1 矩阵继续取证，不要带着「可能是 A 也可能是 B」进入结论。
