---
name: wiki-sync
description: Use when a "wiki nightly sync" autopilot issue fires, when the user types /wiki-sync (run|configure|init|status), or when asked to sync the wiki with release-branch code changes / 夜间 wiki 同步 / 根据代码变更更新 wiki. Orchestrates scheduled and manual pipelines that fetch each configured repo's release-line tip once per collection, computes one-shot range diffs, and drives /wiki-refine --auto to update the D:\wiki 体系, committing the wiki per repo and reporting pending human decisions.
---

# wiki-sync

Scheduled and manual automation that keeps the `/document-systems` wiki 体系 in sync with
release-line code changes. Design agreed in LOC-147: one-shot range diff per repo (never per-commit), auto-accepted
subsystem edits via engine-validated `/wiki-refine --auto`, root/公共化 decisions deferred to a
human via the daily issue, persistent worktrees under `D:\code_sync`, per-repo wiki commits.

Three layers:

1. **Scheduler** — a Multica autopilot (cron `0 0 * * *`, Asia/Shanghai, create_issue) opens the
   nightly issue assigned to the agent; the agent then follows this skill's **Run flow**.
2. **Deterministic collection** — `scripts/wiki_sync.py` (this skill's install dir). No LLM: fetch,
   range-diff, subsystem mapping, noise/structural classification. See `--help` of each subcommand.
3. **Wiki update** — `/wiki-refine --auto --changeset <file>` per repo (its **## `--auto` mode**
   section is the authoritative gate policy; this skill only orchestrates).

The persistent source snapshot and the per-run manifest are different artifacts:

- `<SYNC_WORKTREE>` = `<sync_root>\<domain>\<repo>` (for example
  `D:\code_sync\NP_FMS\fms-protocol`). `materialize` creates or updates this detached worktree
  to the collected `to_sha`; `/wiki-refine --auto` reads source code from here. It is the durable
  daily code snapshot and must not contain generated changeset files.
- `<RUN_DIR>` = one run-scoped directory under the OS temporary root, for example
  `D:\tmp\wiki-sync-<run-id>`. `collect` writes only JSON manifests here: one repo changeset plus
  `_run.json`. A changeset records the one-shot commit/file diff and subsystem signals; it is not
  a second code checkout. Create one directory per run, reuse it for all repos in that run, and
  remove it after the report. If cleanup fails, report the exact path; never retry collection in
  another output directory.

## Paths (resolve once per run)

- `<CONFIG>` = `<wiki_base>\.wiki-sync.json` where `wiki_base` comes from the shared config
  `%USERPROFILE%\.document-systems.json` (default `D:\wiki`). Repo list, per-repo release-line
  `branch`, `last_synced_sha`, optional per-repo `carried_over` state, `code_root` / `sync_root` all
  live there.
- `<SYNC_PY>` = `<this skill's install dir>\scripts\wiki_sync.py`. Always run
  `python -X utf8 <SYNC_PY> ...` (windows-cn-shell-safety applies; Chinese payloads travel through
  files, never the command line).
- Engine + contracts: resolved exactly as `wiki-refine` Phase 1.0.b (document-systems install root).
  If unavailable, abort — same contract-missing message as wiki-refine.

## Subcommands

- `/wiki-sync` or `/wiki-sync run` — the nightly flow below (all enabled repos).
- `/wiki-sync run --repo <domain/repo>` — an explicit manual one-off for one repo. It does not
  apply the nightly 07:30 gate and never creates carry-over entries for other repos.
- `/wiki-sync configure --repo <domain/repo> --branch <branch> --baseline <commit>` — explicit
  branch/baseline switch. The script fetches the branch, resolves the full baseline SHA, verifies
  the baseline is an ancestor of the fetched branch tip, atomically clears stale carry-over state
  and writes the config. Review and commit `.wiki-sync.json` before running sync.
- `/wiki-sync init` — fill null `last_synced_sha` baselines (= current `origin/<branch>` HEAD).
  One-time / after adding a repo to the config. `--force` re-baselines everything (discards any
  pending un-synced range — confirm with the user first).
- `/wiki-sync status` — print per-repo sync state; no side effects.
- `python -X utf8 <SYNC_PY> carry-over --repo <domain/repo> --state <file>` — internal command used
  by the run flow to persist an incomplete/unstarted repo. The UTF-8 JSON state file carries
  `from_sha`, `reason`, and `remaining_subsystems`; `to_sha` is optional/null before that repo is
  fetched, and `detail` is optional.

## Hard Constraints

- NEVER checkout / pull / stash or modify files in the developer working tree under `code_root`
  (`D:\code`). `init`, `configure`, and `collect` may run `git fetch origin <branch>` there. On the first
  materialization, the script runs `git worktree prune` + `git worktree add --detach` against that
  repo's Git metadata to create `<sync_root>\<domain>\<repo>`; later runs execute
  `checkout --detach <to_sha>` inside that sync worktree. `materialize` never fetches.
- NEVER stash or discard uncommitted wiki changes; a dirty `<DOC_REL>` skips that repo tonight.
- All doc edits go through `/wiki-refine --auto` (engine-only); this skill itself edits no doc.
- `last_synced_sha` advances ONLY together with a successful wiki commit for that repo (see step 4
  ordering — the commit includes the config change, so reverting the commit also rolls back the
  pointer and the next night reprocesses the range). `configure` is the explicit exception: it is
  a user-approved branch/baseline reset and must be reviewed as a separate config change.
- Scheduled runs post one issue comment as the report. Manual runs return the report in the current
  session; if a manual run is attached to a Multica issue, post the one issue comment instead. No
  progress comments.

## Daily window contract

- The autopilot starts at 00:00 Asia/Shanghai. The 07:30 gate applies only to scheduled/all-repo
  runs. A user explicitly selecting `--repo` has requested a manual one-off and may start it at
  any time; do not turn that manual request into carry-over state.
- For a scheduled run, check the wall clock immediately after the minimal config/status preflight;
  at or after 07:30, do not load the refine engine, fetch, materialize, or refine any new repo.
- A repo started before 07:30 runs its fetch, every `/wiki-refine --auto` subsystem round, lint,
  and commit to completion even when it crosses 07:30. Repo and subsystem work have NO hard
  timeout. Do not roll back wiki content already applied by a started repo because of the clock.
- After the current repo finishes, a scheduled run persists every unstarted enabled repo as `carried_over` with
  `reason: "not_started_after_0730"`, its current `last_synced_sha` as `from_sha`, `to_sha: null`,
  and an empty `remaining_subsystems` list. Commit the config-only state once, then post the report.
- There is no fixed 10:00 completion guarantee under this policy: report time is current-repo finish
  time plus state/report overhead. Record total elapsed time for every repo so a human can decide
  whether to change the queue, start time, or repository scope.

## Run flow

**1. Determine the invocation mode and perform minimal preflight**

- **Scheduled mode** is `/wiki-sync` or `/wiki-sync run` without `--repo`, including the
  autopilot issue. It processes all enabled repos, applies the 07:30 gate, and may persist
  `carried_over` for repos that were not started.
- **Manual mode** is `/wiki-sync run --repo <domain/repo>`. It processes only that repo, ignores
  the 07:30 gate, and never writes carry-over state for an unselected repo. The explicit `--repo`
  is the user's confirmation that this is an immediate one-off.
- If the requested historical branch or baseline differs from config, stop and run `configure`
  first. Never infer the branch from the developer worktree's current checkout.

- Resolve paths above; `python -X utf8 <SYNC_PY> status` must succeed (config exists — if missing,
  tell the user to create it / run `/wiki-sync init`; do not invent a repo list). Confirm the
  selected row's `branch` and `last_synced_sha` match the requested scope.
- Confirm `D:\wiki\.wiki-sync.json` is tracked and clean before any run. If it is untracked or
  already dirty, stop and ask the user to review/commit or clean the config; do not hide the
  entire config inside a carry-over or wiki commit.
- In scheduled mode, check Asia/Shanghai time now. If it is already 07:30 or later, go directly
  to the carry-over/report path below; do not probe the engine or load refine contracts.
- Before probing the engine, check the selected repo's target `DOC_REL` for uncommitted changes.
  A dirty target is reported as `skipped_dirty` immediately; it does not fetch, create a
  changeset, or load refine contracts. Scheduled mode performs this cheap check for each repo
  immediately after its start gate and can continue to the next clean repo.
- Only after a clean repo is eligible to start, probe the engine (`rule-catalog`) once, same as
  wiki-refine 1.2.b. A manual run reaches this probe only when its selected target is clean,
  regardless of wall clock.

**2. Repo queue**

Read `python -X utf8 <SYNC_PY> status` once. Scheduled mode processes enabled rows in the returned
order; `status` puts persisted `carried_over` repos first and preserves config order within each
group. Manual mode uses only the selected row. Neither mode collects all repos up front: fetch
and wiki update stay serial per repo.

**3. Per-repo processing (serial, isolation per repo)**

For each enabled repo row:

a. **07:30 start gate (scheduled mode only)**: check Asia/Shanghai time before any repo-side action.
   If it is 07:30 or later, mark this row and every later enabled row as unstarted. For each one, write a UTF-8 state
   file with `from_sha = last_synced_sha`, `to_sha = null`,
   `reason = "not_started_after_0730"`, and `remaining_subsystems = []`.
   A row whose `last_synced_sha` is null is reported as `needs_baseline` instead and is not passed
   to `carry-over`. For every valid state, run:

   ```
   python -X utf8 <SYNC_PY> carry-over --repo <domain/repo> --state <state-file>
   ```

   Stop the repo loop. Do not fetch these repos merely to obtain a `to_sha`.
   In manual mode, skip this gate and continue to the dirty check.
b. **Dirty check before collection**: run
   `git -C <wiki_base> status --porcelain -- <domain>/<repo>/`. Non-empty output means
   `skipped_dirty`; record the row and continue without fetch, changeset, worktree
   materialization, or engine/refine work. Never stash or discard those changes.
c. **Start timer + collect**: record `<repo_started_at>` immediately before:

   ```
   python -X utf8 <SYNC_PY> collect --out <RUN_DIR> --repo <domain/repo>
   ```

   Read that repo changeset. `no_change` / `needs_baseline` / `error` are final row statuses for
   tonight; record finish time and continue. Fetch happens only here (or during explicit `init`).
d. **Materialize**: `python -X utf8 <SYNC_PY> materialize --repo <domain/repo> --sha <to_sha>`.
   First use creates the detached worktree via `worktree prune/add`; later runs switch that sync
   worktree with `checkout --detach`. `materialize` never performs another fetch.
e. **Refine to completion**: run `/wiki-refine --auto --changeset <changeset>` from the worktree.
   Do not apply a repo/subsystem timeout and do not stop when 07:30 passes. Collect its JSON report.
   If refine returns an error after applying valid wiki changes, preserve the diff for human review;
   do not roll it back and do not advance `last_synced_sha`.
f. **Commit + advance** - only when the refine report is `ok`:

   ```
   python -X utf8 <SYNC_PY> advance --repo <domain/repo> --sha <to_sha>
   git -C <wiki_base> add <domain>/<repo> .wiki-sync.json
   git -C <wiki_base> commit -m "docs(sync): <domain>/<repo> <from7>..<to7>"
   ```

   If commit fails, restore `last_synced_sha` to `<from_sha>`, unstage only these paths, preserve
   the wiki diff, and report `error`. A successful `advance` clears old carry-over state.
g. **Stop timer**: record `<repo_finished_at>` and elapsed seconds after the final repo status is
   known. The elapsed value includes fetch, materialize, refine, lint, state update, and commit.

After the loop, if new carry-over states were written in scheduled mode, commit `.wiki-sync.json`
once with `docs(sync): carry over unstarted repos <YYYY-MM-DD>`. Include that state commit in the
report. Manual mode never creates this config-only commit. After the report, remove `<RUN_DIR>`;
if removal fails, include the path and cleanup error in the report without rerunning collection.

**4. Report**

For scheduled mode, post ONE issue comment immediately after the current repo finishes and
unstarted state is persisted (`--content-file`, per platform rules). For manual mode, return the
same report in the current session; if the caller supplied a Multica issue context, post that one
comment instead. There is no report deadline independent of current-repo completion:

```markdown
## wiki 夜间同步报告 <YYYY-MM-DD>

执行窗口：<run_started_at> -> <run_finished_at>（总耗时 <duration>）

| 仓 | 范围 | commits | 子系统 | 更新文档 | §10 | 耗时 | 状态 |
|---|---|---|---|---|---|---|---|
| NP_FMS/fms-server | 7b8aade..1a2b3c4 | 12 | fms-core | 2 | 1 | 42m18s | 已提交 |
| ... | | | | | | 0s | no_change / skipped_dirty / carried_over / error / 未启动 |

### 待人工决策（N 项）
- [仓] <摘要与证据>

### 结构性变更（建议走 /document-systems）
- [仓] <signal>

### 跳过 / 失败 / 7:30 后未启动
- [仓] <原因>（last_synced_sha 未推进；下次优先处理）
```
Omit empty sections. Include the wiki commit hashes so the user can `git -C D:\wiki show <hash>`
or revert a single repo's night.

## Error recovery

| Failure | Action |
|---|---|
| config missing / repo not in config | Report, no side effects; suggest editing `<CONFIG>` + `/wiki-sync init` |
| config untracked or dirty | Stop before collection; ask the user to review and commit/clean `.wiki-sync.json` |
| requested branch/baseline differs from config | Stop; run `/wiki-sync configure --repo ... --branch ... --baseline ...`, review and commit the config, then retry |
| target Wiki path dirty | Report `skipped_dirty` before collection; do not fetch or create a changeset |
| changeset output failure | Report `error`; do not retry collection in another directory; report `<RUN_DIR>` if cleanup also fails |
| fetch timeout / auth failure on one repo | That repo → `error` in report; others proceed |
| `needs_baseline` | Report; run `/wiki-sync init` (only fills nulls) |
| history rewritten (force-push) | Changeset carries the flag; refine proceeds on the net diff; flag shown in report |
| worktree path exists but broken | Script refuses; report tells user to remove `<sync_root>\<域>\<仓>` manually |
| wiki dirty under a repo | `skipped_dirty`; never stash |
| 07:30 reached between repos | Do not start/fetch remaining repos; persist them with `to_sha: null`, finish state commit, then report |
| manual `/wiki-sync run --repo ...` after 07:30 | Run the selected repo immediately; never create carry-over for this manual request |
| current repo crosses 07:30 | Continue every subsystem and commit to completion; no timeout and no rollback |
| refine error after valid edits | Preserve the wiki diff for human review; no advance and no automatic rollback |

## What this skill does NOT do

- No doc editing of its own (that is `/wiki-refine --auto`); no Discovery / regeneration (that is
  `/document-systems`, human-triggered on structural signals).
- No developer working-tree content mutation. It does fetch source Git metadata and manage linked
  worktree metadata exactly as described in Hard Constraints.
- No generated changeset files in `sync_root`; source worktrees stay clean and detached at the
  collected code SHA. Run manifests live only under `<RUN_DIR>` and are cleaned after reporting.
- No implicit branch/baseline changes. Use the explicit `configure` operation for a historical
  Wiki baseline; do not use `init --force` to switch branches or recover a range. `init --force`
  remains a destructive all-repo re-baseline and requires separate confirmation.
