# 安装 Bash-guard hook（首次安装时做一次）

`windows-cn-shell-safety` 里「Bash vs PowerShell 工具边界」是给 agent 看的软约束。这个 hook 在**系统层**把它兜底：agent 往 **Bash 工具**里塞 PowerShell 专属语法（`Remove-Item`、`$env:`、`-ErrorAction` 等）时，直接拦下这次调用并提示改用 PowerShell 工具，不依赖 agent 自觉。

**一次性配置。** 在一台 Windows 机器上部署本 skill 时配一次即可，平时用 skill 不需要再读本文件。Claude Code 与 Codex 两个 harness 各配一遍，脚本共用一份。

## 脚本

`../hooks/block-powershell-in-bash.ps1`（本 skill 目录内，UTF-8 **with BOM**）。逻辑：读 stdin JSON → 取 `tool_input.command` → 大小写不敏感、词边界匹配 PowerShell 关键字 → 命中则向 stderr 打中文提示并 **exit 2**（两个 harness 都用 exit 2 表示「拦截」，stderr 会回传给模型）；未命中 exit 0 放行。

把脚本复制到两个 harness 的全局 hooks 目录（`<用户名>` 换成实际用户名，本机是 `admin`）：

```bash
mkdir -p /c/Users/<用户名>/.claude/hooks /c/Users/<用户名>/.codex/hooks
cp "<本skill目录>/hooks/block-powershell-in-bash.ps1" /c/Users/<用户名>/.claude/hooks/
cp "<本skill目录>/hooks/block-powershell-in-bash.ps1" /c/Users/<用户名>/.codex/hooks/
# 校验 BOM：前 3 字节应为 ef bb bf
head -c 3 /c/Users/<用户名>/.claude/hooks/block-powershell-in-bash.ps1 | od -An -tx1
```

> 必须带 BOM。WinPS 5.1（本机无 pwsh）解析无 BOM 的 UTF-8 `.ps1` 会按 GBK 读，中文提示直接乱码。

## Claude Code —— 全局 `~/.claude/settings.json`

把下面 **并入**（不是覆盖！）已有的 `hooks` 对象：

```json
"PreToolUse": [
  {
    "matcher": "Bash",
    "hooks": [
      {
        "type": "command",
        "command": "powershell.exe",
        "args": ["-NoProfile","-ExecutionPolicy","Bypass","-File","C:\\Users\\<用户名>\\.claude\\hooks\\block-powershell-in-bash.ps1"],
        "timeout": 15,
        "statusMessage": "Checking Bash command for PowerShell syntax..."
      }
    ]
  }
]
```

- 全局 hook 的脚本路径写**绝对路径**，别用 `${CLAUDE_PROJECT_DIR}`（那个指向当前项目，不是全局脚本）。
- Claude Code 里 PreToolUse **只有 exit 2 才拦截**；exit 1 是非阻断错误，不会拦。
- 全局 settings.json 通常已有 `env`、别的 hooks、plugins 等，编辑前先读、只加 `PreToolUse`、别动其它键。

## Codex —— `~/.codex/config.toml`

追加（TOML 用**单引号字面串**，Windows 反斜杠不用转义）：

```toml
[[hooks.PreToolUse]]
matcher = "^Bash$"

[[hooks.PreToolUse.hooks]]
type = "command"
command = 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\Users\<用户名>\.codex\hooks\block-powershell-in-bash.ps1"'
timeout = 15
statusMessage = "Checking Bash command for PowerShell syntax..."
```

- `matcher` 是对 `tool_name` 的正则；shell 执行的规范名是 `Bash`，`^Bash$` 与 Claude Code 侧一致。
- Codex 的阻断契约与 Claude Code 相同：**exit 2 + stderr** 即拦截（Codex 另支持 stdout JSON `permissionDecision:"deny"`，本脚本用 exit 2 一套通吃）。
- **信任门槛**：`~/.codex/config.toml` 里的是「非托管」hook，装完要在 Codex 里跑一次 `/hooks` 审核并**信任**它，普通会话才会生效；自动化里可临时加 `codex exec --dangerously-bypass-hook-trust`。改了 hook 定义会掉信任、需重新 `/hooks`。

## 验证

不经 harness、直接喂 payload 给脚本（最稳，先确认脚本本身 OK）——**从 PowerShell 工具跑**，避免被 Bash 侧的同款 hook 拦到自己的测试命令：

```powershell
'{"tool_name":"Bash","tool_input":{"command":"Remove-Item ./x"}}' | powershell.exe -NoProfile -ExecutionPolicy Bypass -File <脚本>
"exit=$LASTEXITCODE"   # 期望：中文提示 + exit 2
'{"tool_name":"Bash","tool_input":{"command":"rm ./x"}}'          | powershell.exe -NoProfile -ExecutionPolicy Bypass -File <脚本>
"exit=$LASTEXITCODE"   # 期望：无输出 + exit 0
```

harness 端到端：Claude Code 在 Bash 工具跑 `Remove-Item ./x` 应被拦、`rm ./x` 应放行；Codex 在 `/hooks` 信任后，让它用 shell 跑含 `Remove-Item` 的命令应被拦。
