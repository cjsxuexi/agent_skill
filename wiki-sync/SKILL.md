---
name: wiki-sync
description: Use when a "wiki nightly sync" autopilot issue fires, when the user types /wiki-sync (run|init|status), or when asked to sync the wiki with release-branch code changes / 夜间 wiki 同步 / 根据代码变更更新 wiki. Orchestrates the nightly pipeline that pulls each configured repo's release-line branch, computes one-shot range diffs, and drives /wiki-refine --auto to update the D:\wiki 体系, committing the wiki per repo and reporting pending human decisions on the issue.
---

# wiki-sync

Nightly automation that keeps the `/document-systems` wiki 体系 in sync with release-line code
changes. Design agreed in LOC-147: one-shot range diff per repo (never per-commit), auto-accepted
subsystem edits via engine-validated `/wiki-refine --auto`, root/公共化 decisions deferred to a
human via the daily issue, persistent worktrees under `D:\code_sync`, per-repo wiki commits.

Three layers:

1. **Scheduler** — a Multica autopilot (cron `0 2 * * *`, Asia/Shanghai, create_issue) opens the
   nightly issue assigned to the agent; the agent then follows this skill's **Run flow**.
2. **Deterministic collection** — `scripts/wiki_sync.py` (this skill's install dir). No LLM: fetch,
   range-diff, subsystem mapping, noise/structural classification. See `--help` of each subcommand.
3. **Wiki update** — `/wiki-refine --auto --changeset <file>` per repo (its **## `--auto` mode**
   section is the authoritative gate policy; this skill only orchestrates).

## Paths (resolve once per run)

- `<CONFIG>` = `<wiki_base>\.wiki-sync.json` where `wiki_base` comes from the shared config
  `%USERPROFILE%\.document-systems.json` (default `D:\wiki`). Repo list, per-repo release-line
  `branch`, `last_synced_sha` state, `code_root` / `sync_root` all live there.
- `<SYNC_PY>` = `<this skill's install dir>\scripts\wiki_sync.py`. Always run
  `python -X utf8 <SYNC_PY> ...` (windows-cn-shell-safety applies; Chinese payloads travel through
  files, never the command line).
- Engine + contracts: resolved exactly as `wiki-refine` Phase 1.0.b (document-systems install root).
  If unavailable, abort — same contract-missing message as wiki-refine.

## Subcommands

- `/wiki-sync` or `/wiki-sync run` — the nightly flow below (all enabled repos).
- `/wiki-sync run --repo <domain/repo>` — same flow, one repo.
- `/wiki-sync init` — fill null `last_synced_sha` baselines (= current `origin/<branch>` HEAD).
  One-time / after adding a repo to the config. `--force` re-baselines everything (discards any
  pending un-synced range — confirm with the user first).
- `/wiki-sync status` — print per-repo sync state; no side effects.

## Hard Constraints

- NEVER checkout / pull / stash / mutate anything under `code_root` (`D:\code`) — developer
  working trees. Source repos are touched by `git fetch` only (the script guarantees this).
- NEVER stash or discard uncommitted wiki changes; a dirty `<DOC_REL>` skips that repo tonight.
- All doc edits go through `/wiki-refine --auto` (engine-only); this skill itself edits no doc.
- `last_synced_sha` advances ONLY together with a successful wiki commit for that repo (see step 4
  ordering — the commit includes the config change, so reverting the commit also rolls back the
  pointer and the next night reprocesses the range).
- One issue comment per run (the report). No progress comments.

## Run flow

**1. Preflight**

- Resolve paths above; `python -X utf8 <SYNC_PY> status` must succeed (config exists — if missing,
  tell the user to create it / run `/wiki-sync init`; do not invent a repo list).
- Probe the engine (`rule-catalog`), same as wiki-refine 1.2.b.

**2. Collect (deterministic)**

```
python -X utf8 <SYNC_PY> collect --out .\changesets
```

Read `.\changesets\_run.json`. Buckets per repo `status`: `changes` → process; `no_change` /
`needs_baseline` / `error` → report only (a `needs_baseline` repo means init was never run for it).

**3. Per-repo processing (serial, isolation per repo)**

For each repo with `status: "changes"`, in config order:

a. **Dirty check**: `git -C <wiki_base> status --porcelain -- <domain>/<repo>/` non-empty → mark
   `skipped_dirty`, continue to next repo.
b. **Materialize**: `python -X utf8 <SYNC_PY> materialize --repo <domain/repo> --sha <to_sha>` —
   persistent detached worktree at `<sync_root>\<domain>\<repo>` (created on first use, reused
   nightly, never deleted).
c. **Refine**: run `/wiki-refine --auto --changeset .\changesets\<domain>__<repo>.json` from the
   worktree. Its `--auto` section owns all gate policy (auto-accept subsystem txns, §10 +
   `pending_decisions` for root/公共化, escalation auto-reject, engine lint instead of opus
   review). Collect the returned JSON report.
   - **Scale guard**: a subsystem bucket with a very large file list is still ONE topic — pass the
     per-file stats but let the refine subagent read selectively; if the whole changeset cannot be
     finished tonight (context/time), stop cleanly after the last fully-processed subsystem, mark
     the repo `carried_over`, and do NOT advance — next night re-collects the same (grown) range.
d. **Commit + advance (atomic pair)** — only when the refine report is `ok`:

```
python -X utf8 <SYNC_PY> advance --repo <domain/repo> --sha <to_sha>
git -C <wiki_base> add <domain>/<repo> .wiki-sync.json
git -C <wiki_base> commit -m "docs(sync): <domain>/<repo> <from7>..<to7>"
```

   If the commit fails: `advance` back to `<from_sha>`, `git -C <wiki_base> reset` the staged
   paths, mark the repo `error`, continue.
e. On refine `skipped_dirty` / `error`: no advance, no commit; record and continue.

**4. Report (one issue comment, mandatory)**

Post ONE comment on the triggering issue (UTF-8 file + `--content-file`, per platform rules):

```markdown
## wiki 夜间同步报告 <YYYY-MM-DD>

| 仓 | 范围 | commits | 子系统 | 更新文档 | §10 | 状态 |
|---|---|---|---|---|---|---|
| NP_FMS/fms-server | 7b8aade..1a2b3c4 | 12 | fms-core, fms-gateway | 2 | 1 | ✅ 已提交 |
| ... | | | | | | no_change / skipped_dirty / carried_over / error |

### 待人工决策（N 项）
- [NP_FMS/fms-server] root_updates/mermaid_edge：<摘要>。证据：<...>（已记入 §10）
- （处理方式：回复本 issue 说明决定，或在人工 /wiki-refine 会话中应用）

### 结构性变更（建议走 /document-systems）
- [域/仓] <signal> → 建议 `/document-systems --only=<子系统>`（人工确认后执行）

### 跳过 / 失败
- [域/仓] <原因>（该仓 last_synced_sha 未推进，明晚自动重试同一范围）
```

Omit empty sections. Include the wiki commit hashes so the user can `git -C D:\wiki show <hash>`
or revert a single repo's night.

## Error recovery

| Failure | Action |
|---|---|
| config missing / repo not in config | Report, no side effects; suggest editing `<CONFIG>` + `/wiki-sync init` |
| fetch timeout / auth failure on one repo | That repo → `error` in report; others proceed |
| `needs_baseline` | Report; run `/wiki-sync init` (only fills nulls) |
| history rewritten (force-push) | Changeset carries the flag; refine proceeds on the net diff; flag shown in report |
| worktree path exists but broken | Script refuses; report tells user to remove `<sync_root>\<域>\<仓>` manually |
| wiki dirty under a repo | `skipped_dirty`; never stash |
| refine incomplete (context/time) | `carried_over`; no advance; next night re-collects the grown range |

## What this skill does NOT do

- No doc editing of its own (that is `/wiki-refine --auto`); no Discovery / regeneration (that is
  `/document-systems`, human-triggered on structural signals).
- No source-repo mutation beyond `git fetch` + worktrees under `sync_root`.
- No re-baselining without explicit user request (`init --force`).
