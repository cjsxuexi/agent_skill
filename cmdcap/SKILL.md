---
name: cmdcap
description: >-
  Use when you must run diagnostic commands on a Linux server reached only
  through a JumpServer bastion's Luna web terminal (you cannot SSH in, the target
  cannot reach the user's machine) and need the command output back as files
  instead of the user pasting it — especially large or multi-command output.
  Triggers: JumpServer, 堡垒机, Luna web terminal, bastion target, "can't SSH to
  the server", "paste the output", capturing remote command output for the agent.
---

# cmdcap — capture remote command output through JumpServer

## Overview

You are driving diagnostics on a Linux server that sits **behind a JumpServer bastion**. The user reaches it only through the **Luna web terminal** in a browser; you cannot SSH in, and the target cannot reach the user's machine. `cmdcap` records the target shell session and writes clean, per-command text dumps the user downloads via Luna into `C:\Users\admin\Downloads\`, which you read.

Tool + prebuilt binary live at `D:\jk_file\skills\cmdcap\` (linux/amd64 at `dist\cmdcap-linux-amd64`; full docs in `./README.md`).

## Mental model — get this right

Run, in order, **inside the Luna terminal**:

1. **`cmdcap shell`** — once per session. Starts a *recorded subshell*; the user then works normally inside it.
2. Diagnostic commands — run them **normally**, as if typed.
3. **`cmdcap save`** — flushes the new rounds to a file and prints its path.
4. `exit` — ends recording.

**`cmdcap save` is a flush command, NOT a wrapper, and NOT an end-of-session step:**

- ❌ It takes **no command argument**. Never write `cmdcap save df -h`.
- ❌ Do **not** put it after `exit`. It runs *inside* the recorded shell.
- ✅ Run the command, then `cmdcap save` **on its own**.

It is **incremental**: each `save` returns only the rounds since the previous save (a cursor advances). Call `save` after each batch and you get exactly that batch — never re-grabbing old output.

## How you issue commands — the rule

When you hand the user commands, put **each diagnostic command on its own line**, then **`cmdcap save` alone on the final line**:

✅ correct
```
kubectl get pods -n port
systemctl status docker
cmdcap save
```

❌ wrong — never join with `;` (cmdcap treats one line = one round, so this both pollutes the round and is not recognized as a save):
```
kubectl get pods -n port ; cmdcap save
```

Then tell the user: download the printed file via Luna into `C:\Users\admin\Downloads\` and say when it has landed.

## First time on a new target — install

Check first — have the user run:
```
command -v cmdcap || echo MISSING
```
If missing:
1. In Luna's file manager, upload `D:\jk_file\skills\cmdcap\dist\cmdcap-linux-amd64` to the target home directory.
2. `mv ~/cmdcap-linux-amd64 ~/cmdcap && chmod +x ~/cmdcap`
3. Invoke as `~/cmdcap` (or `export PATH=$HOME:$PATH` once, then `cmdcap`).

Needs `bash` on the target (normally present). Inside `cmdcap shell`, `cmdcap` is already on PATH.

## Reading the result

Read the **newest** file in `C:\Users\admin\Downloads\`. Recursive glob is unreliable on this machine — list by modified time instead:
```
Get-ChildItem C:\Users\admin\Downloads\cap-*.txt | Sort-Object LastWriteTime | Select-Object -Last 1
```
Each dump pairs every command with its output:
```
[#6] $ systemctl status docker    (exit=0  cwd=/home/x  2026-06-24 09:01:22)
----------------------------------------------------------------
<output>
```

## save options (quick ref)

| command | use |
|---|---|
| `cmdcap save` | new rounds since last save (default, incremental) |
| `cmdcap save -n 3` | last 3 rounds |
| `cmdcap save --from 5 --to 7` | re-grab an explicit round range (does NOT move the cursor) |
| `cmdcap save --tail 100` | keep only the last 100 output lines per round |
| `cmdcap status` | session id, round counts, cursor |

## Boundaries & gotchas

- **Line-oriented commands only.** Full-screen TUIs (`vim`, `top`, interactive `less`) capture as garbage — don't run cmdcap around those.
- One Luna download per save (bastion isolation — the target can't push to the user's machine).
- After `cmdcap shell`, wait for the new prompt before running commands; pasting a multi-line block is fine.
- A `cmdcap: warning: ... could not be sliced` message means a round was lost (rare) — re-run that command.
- `cmdcap` itself is never captured as a round (its own commands are filtered out).

## Common mistakes

| Mistake | Fix |
|---|---|
| `cmdcap save <cmd>` (save as a wrapper) | save takes NO command — run the command, then `cmdcap save` alone |
| `cmdcap save` after `exit` | run it **inside** the recorded shell, before exit |
| `cmd ; cmdcap save` on one line | separate lines; `cmdcap save` must be its own line |
| Expecting old output from a plain `save` | default is incremental; use `--from/--to` to re-grab |
| Reading a stale inbox file | sort by LastWriteTime, take the newest |

Full design / rationale: `../plan/2026-06-22-cmdcap-jumpserver-capture-design.md`.
