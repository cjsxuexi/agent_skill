# cmdcap — JumpServer 命令/输出捕获

把 JumpServer (Luna Web 终端) 目标机上的「命令+输出」按轮次存成干净文本，
经 Luna SFTP 下载到本地 `C:\Users\admin\Downloads\`，供 Claude 读取。

## 安装（每台目标机一次）

1. Luna 文件管理 → 上传 `cmdcap-linux-amd64` 到目标机 `~/`。
2. 在目标机终端：
   ```
   mv ~/cmdcap-linux-amd64 ~/cmdcap && chmod +x ~/cmdcap
   ```
   之后用 `~/cmdcap` 调用（或 `export PATH="$HOME:$PATH"` 后直接 `cmdcap`）。

## 每次使用

1. 进会话后开录：
   ```
   ~/cmdcap shell
   ```
   进入一个被录制的子 shell（照常敲命令，`cd`/管道/builtin 均正常；
   子 shell 内 `cmdcap` 已在 PATH）。
2. 正常执行 Claude 给的命令。想取回结果时，单独一行执行：
   ```
   cmdcap save
   ```
   它把上次保存之后的新轮次写成 `~/cmdcap-out/cap-<ts>-<from>-<to>.txt` 并打印路径。
3. Luna 下载该文件到 `C:\Users\admin\Downloads\`，告诉 Claude「读最新的」。
4. 结束：`exit`。

## save 选项

| 命令 | 含义 |
|---|---|
| `cmdcap save` | 增量：上次保存之后的新轮次（默认，不重复） |
| `cmdcap save -n 3` | 最近 3 轮 |
| `cmdcap save --from 5 --to 7` | 指定区间（补取旧内容；不移动游标） |
| `cmdcap save --tail 100` | 每轮只保留末尾 100 行 |
| `cmdcap status` | 看会话、轮次数、游标 |

## 约定（Claude 发命令时）

诊断命令各占一行，最后单独一行 `cmdcap save`。不要写 `cmd ; cmdcap save`
同行（会并成一条 history、污染命令文本与输出）。

## 边界

- 面向行式诊断命令（ps/cat/tail/curl/kubectl get/看日志）。
- 全屏 TUI（vim/top/交互式 less）刷屏，去 ANSI 后仍乱，不适合捕获。
- `save` 不重跑命令、无副作用。
- 需目标机有 `bash`；每条命令后终端会多出一行明文标记（切片用，可接受）。
- 每次保存需在 Luna 手动下载一次（堡垒机隔离的固有代价）。
