---
name: windows-cn-shell-safety
description: >-
  Use when running Python or PowerShell on Windows where commands may touch
  Chinese paths, Chinese filenames, or non-ASCII content. Also use after seeing
  `UnicodeEncodeError: 'gbk' codec ...`, `OSError: Invalid argument` on a Chinese
  path, garbled `[garbled filename]` paths, `Unrecognized escape sequence \U` from
  PowerShell `Select-String`, or before invoking `python3 scripts/...` in
  Chinese-content repos. Covers interpreter detection, path safety, PowerShell
  regex pitfalls, and manifest CSV writes.
---

# windows-cn-shell-safety

Operational rules for running Python and PowerShell commands on Windows when the workload involves Chinese paths, Chinese filenames, or other non-ASCII content. Compiled from incidents while parsing `.mhtml` knowledge-base exports for `fabusurfer/document/port-data/`.

These rules are **flexible**: apply the spirit, not the letter. If you understand why a rule exists, adapt it to the new case.

## When to apply

Any of:

- About to run `python <script>` or `python3 <script>` that reads or writes files with Chinese paths or filenames.
- About to run PowerShell `Select-String`, or any regex containing a Windows path like `C:\Users\...`.
- About to write or parse a manifest CSV that may contain Chinese filenames.
- Encountered any of these errors:
  - `UnicodeEncodeError: 'gbk' codec can't encode character ...`
  - `OSError: Invalid argument` on a path whose display looks like `[garbled filename]`
  - `Unrecognized escape sequence \U` from a PowerShell regex

## Rule 1 — Probe `python` first, then `python3`

Windows installers expose `python.exe` and usually do NOT expose `python3.exe`. **Probe `python` first; fall back to `python3` only if `python` is unavailable.** Never hardcode either name as the only option.

PowerShell pattern:

```powershell
$py = if (Get-Command python  -ErrorAction SilentlyContinue) { 'python' }
      elseif (Get-Command python3 -ErrorAction SilentlyContinue) { 'python3' }
      else { throw 'No python interpreter found' }
& $py @args
```

This is the opposite of the Linux/macOS convention (which is `python3` first). On Windows, follow the rule above.

## Rule 2 — Never hardcode Chinese paths into Python source literals

Chinese path strings can be silently mangled when passed through PowerShell here-strings into `python -c`. Symptom: the path arrives in Python as `[garbled filename]`, and reads fail with `OSError: Invalid argument`.

Preferred patterns, in order:

1. **Directory enumeration** — let Python find the file from a known parent:
   ```python
   from pathlib import Path
   mhtml = next(Path(r'D:/code/fabusurfer_raw/provided').glob('*.mhtml'))
   ```
2. **Command-line arguments** — pass the resolved path from PowerShell:
   ```powershell
   python parse.py (Resolve-Path '.\中文.mhtml').Path
   ```
3. **PowerShell `Resolve-Path`** before invoking Python, then use the resolved path string.

Never put a Chinese path literal inside a `python -c '...'` here-string. Never embed a Chinese path literal inside a `.py` script you compose in the same here-string.

## Rule 3 — `Select-String` interprets backslashes as regex escapes

A pattern like `C:\Users\admin\...` triggers `Unrecognized escape sequence \U` because `\U` reads as a Unicode escape to the regex engine.

Fixes:

- Use `-SimpleMatch` when the pattern is a literal:
  ```powershell
  Select-String -SimpleMatch 'C:\Users\admin\foo' file.txt
  ```
- For CSV manifests, parse with `Import-Csv` and filter by column equality — no regex needed.

## Rule 4 — Write manifests via CSV libraries, not string concatenation

Manifests with Chinese filenames, commas in fields, or Windows backslashes break naive string joins. Use:

- Python: `csv.writer` or `csv.DictWriter` with `newline=''` and `encoding='utf-8'`.
- PowerShell: `Import-Csv` / `Export-Csv` with `-Encoding UTF8`.

## Rule 5 — Console encoding fallback

`PYTHONIOENCODING=utf-8` is set globally at the Windows user level and in Claude Code `settings.json`, and via `[shell_environment_policy].set` in `~/.codex/config.toml`. Subprocesses inherit it.

If a stubborn `UnicodeEncodeError: 'gbk' codec ...` still surfaces (rare — usually means a process started before the env var was set), run `chcp 65001` once in the current PowerShell session as a fallback. Restart the offending process to pick up the persistent env var on the next try.

## What this skill does NOT cover

- Linux/macOS shells (rules are Windows-specific).
- General Python text-encoding theory.
- Non-CJK locales — Japanese/Korean may share some quirks but are not tested here.

## Reference

Original incident log: `D:\code\fabusurfer\document\skill_suggest.md` *(removed ~2026-06 — fabusurfer's `document/` dir was deleted from the repo; the file no longer exists at any path. The rules in this skill are now the source of truth.)*

### multica CLI 发评论：固定用 Write tool + PowerShell

本项目已固化的评论流程（防止 PowerShell 5.1 piping 丢中文）：

1. 用 **Write tool** 把内容写入 UTF-8 文件（如 `reply.md`）
2. 用 **PowerShell 工具** 执行：`multica issue comment add <id> --content-file ./reply.md`
3. 用 **PowerShell 工具** 清理：`Remove-Item ./reply.md`

不要用 Bash 工具执行 multica 评论命令，因为管道编码问题在 Bash 侧同样存在（通过 winpty 桥接时可能丢失非 ASCII）。

## Bash vs PowerShell 工具边界

选工具看**操作目的**，不看操作系统。

### 决策规则（优先级从高到低）

| 场景 | 用哪个工具 |
|------|-----------|
| git 操作（commit / status / diff / push） | **Bash** |
| 运行 shell 脚本（.sh）、grep / find / awk | **Bash** |
| 读写文件（cat / rm / cp / mv），路径无空格无中文 | **Bash** |
| Windows 原生命令（Get-ChildItem、icacls、Start-Process） | **PowerShell** |
| 路径含空格或中文字符 | **PowerShell**（避免 Git Bash 路径转义问题） |
| 写文件后用 multica CLI 提交（防中文乱码） | **PowerShell**（Write tool 写文件 + PowerShell 执行） |
| npm / node / python（无中文路径） | **Bash** |

### 最容易混淆的命令对照表

| 操作 | Bash 工具（✅） | PowerShell 工具（✅） | 常见错误 |
|------|---------------|---------------------|----|
| 删除文件 | `rm ./reply.md` | `Remove-Item ./reply.md` | 在 Bash 里用 `Remove-Item` → `command not found` |
| 列目录 | `ls -la` | `Get-ChildItem` 或 `ls`（别名） | — |
| 多行字符串 | `` cat <<'EOF'``...`EOF` | `@'`...`'@`（列 0 对齐） | 在 Bash 里用 `@'...'@` → 语法报错 |
| 读文件内容 | `cat file.txt` | `Get-Content file.txt` | — |
| 设置环境变量 | `export FOO=bar` | `$env:FOO = 'bar'` | 在 PowerShell 里用 `export` → 无效 |

### git commit 多行消息

git 操作统一用 **Bash 工具**，多行消息用标准 heredoc：

```bash
git commit -m "$(cat <<'EOF'
Fix login redirect bug

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

### 一句话记忆

> **Bash = Unix 世界（git、脚本、纯 ASCII 路径）；PowerShell = Windows 世界（原生 API、中文路径、multica CLI 提交）。拿不准就看路径里有没有中文或空格：有就用 PowerShell。**

**系统层兜底（一次性）**：这条边界另有一个全局 PreToolUse hook（`hooks/block-powershell-in-bash.ps1`，随本 skill 附带）在 Claude Code / Codex 里做系统层拦截。**仅在首次给某台机器安装本 skill 时**配置一次，步骤见 `references/install-bash-guard-hook.md`；平时用本 skill 无需关心它。
