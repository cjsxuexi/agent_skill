# PreToolUse hook: block PowerShell-only syntax typed into a "Bash" tool call.
#
# Shared by BOTH agent harnesses on Windows + Git Bash:
#   - Claude Code : hooks.PreToolUse (matcher "Bash")      in ~/.claude/settings.json
#   - Codex CLI   : [[hooks.PreToolUse]] (matcher "^Bash$") in ~/.codex/config.toml
#
# Why: agents sometimes type PowerShell-only syntax (Remove-Item, $env:, ...) into the
# Bash tool, which then fails with "command not found". This hook scans the command
# BEFORE it runs and, on a hit, blocks the call and tells the agent to use PowerShell.
#
# Blocking contract (identical for both harnesses):
#   exit 0            -> allow the command (no interference)
#   exit 2 + stderr   -> BLOCK the tool call; stderr is fed back to the model as the reason
#   any other code    -> non-blocking error (does NOT block) -> never used here
#
# Both Claude Code and Codex put the shell command at tool_input.command on the stdin
# JSON, and both honor "exit 2 + stderr" as a block, so one script serves both.

$ErrorActionPreference = 'Stop'

# --- Read the hook payload from stdin, decoded explicitly as UTF-8 ---------------
# (Do not rely on the console code page: on zh-CN Windows it is GBK by default.)
try {
    $stdinStream = [Console]::OpenStandardInput()
    $reader      = New-Object System.IO.StreamReader($stdinStream, [System.Text.Encoding]::UTF8)
    $raw         = $reader.ReadToEnd()
    $reader.Dispose()
} catch {
    # If we cannot even read stdin, never block the user's command.
    exit 0
}

if ([string]::IsNullOrWhiteSpace($raw)) { exit 0 }

# --- Extract tool_input.command --------------------------------------------------
try {
    $command = ($raw | ConvertFrom-Json).tool_input.command
} catch {
    exit 0
}
if ([string]::IsNullOrWhiteSpace($command)) { exit 0 }

# --- PowerShell-only tokens to detect (case-insensitive) -------------------------
# Verb-Noun cmdlets are matched with word boundaries (\b) so they only trip on the
# whole token, not as a substring of some unrelated identifier. The parameter-style
# tokens (-ErrorAction, -Confirm:) and the $env: variable scope are distinctive
# enough that a literal match is safe and unlikely to hit legitimate bash.
$pattern = '(?i)(' +
    '\bRemove-Item\b|\bGet-ChildItem\b|\bNew-Item\b|\bSet-Content\b|\bGet-Content\b|' +
    '\bWrite-Host\b|\bWrite-Output\b|\bOut-File\b|\bCopy-Item\b|\bMove-Item\b|' +
    '\bRename-Item\b|\bTest-Path\b|\bConvertFrom-Json\b|\bConvertTo-Json\b|' +
    '-ErrorAction\b|-Confirm:|\$env:' +
    ')'

$m = [regex]::Match($command, $pattern)
if ($m.Success) {
    $msg = "[Hook] Bash 工具检测到 PowerShell 语法: " + $m.Value + " — 请改用 PowerShell 工具"
    # Emit the reason on stderr as UTF-8 so the harness shows the block message intact.
    $errStream = [Console]::OpenStandardError()
    $writer    = New-Object System.IO.StreamWriter($errStream, (New-Object System.Text.UTF8Encoding($false)))
    $writer.WriteLine($msg)
    $writer.Flush()
    $writer.Dispose()
    exit 2
}

exit 0
