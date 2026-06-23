---
name: document-systems
description: Slash command /document-systems. Generates Chinese architecture documentation into a configurable wiki directory (default D:\wiki, asked on first run) for every subsystem of a multi-module repository (Java / frontend / Node / Python), or one document for a single-system repo via --single. Manual command — invoke only when the user types /document-systems exactly; do not infer this skill from any natural-language request.
---

# document-systems

Generates and refreshes Chinese architecture documentation for every subsystem in the current repository, plus an optional global root-level overview — or, in single mode (`--single`), one `§1–§10` document for a one-system repo (see **Mode** below). The main agent NEVER reads subsystem source code directly — it only performs light preparation, owns scheduling, writes the root document, and dispatches subagents for subsystem work. This keeps main context light (< 50K tokens for repos with 20+ modules) and enforces dependency-respecting analysis order.

## Arguments

- `--force` — run the full initialization/regeneration flow: Discovery/topology, root document, all subsystem documents, review. This overwrites `<DOC_ROOT>/.progress.json` with a fresh v2 manifest.
- `--only=<name>` — update only the named subsystem document, then run review by default. The subsystem must exist in the saved v2 manifest.
- `--step=<list>` — execute selected steps. `<list>` is comma-separated and may contain `discovery`, `root`, `subsystems`, `review`, or `all`.
- `--no-discovery` — remove `discovery` from an explicit step list such as `--step=all`; invalid with `--force`.
- `--reconfigure` — re-ask the wiki base location (see Phase 1.0) and overwrite the saved config, then proceed.
- `--single` — document the current folder as ONE system (single-system mode): produce a single `§1–§10` document at `<DOC_ROOT>/architecture.md`, skipping Discovery, the root 系统总览, and per-subsystem subdirs. Set at initialization and recorded in `.progress.json`; later default runs reuse it. Without this flag the mode is multi-subsystem (current behavior). See **Mode** below.
- `--init-domains` — interactively create/edit the domain whitelist in `<WIKI_BASE>/.wiki.json` (via `resolve-domain --set`), then exit WITHOUT generating docs.
- `--domain-index[=<domain>]` — rebuild only the domain landing index `<WIKI_BASE>/<domain>/index.md` (engine `update-domain-index`), then exit. Omitted value = the domain this repo resolves to.

Default behavior (multi mode):

- `/document-systems` defaults to `--step=subsystems,review` and skips Discovery/topology.
- `/document-systems --only=<name>` defaults to `--step=subsystems,review` for that one subsystem.
- `/document-systems --force` defaults to `--step=all`.

Step rules (multi mode):

- `all` expands to `discovery,root,subsystems,review`.
- Discovery runs ONLY when `--force` is used or when `--step` explicitly includes `discovery`.
- Do not combine `--force` with `--only`, `--no-discovery`, or a narrow `--step` other than omitted / `all`. Abort with a clear Chinese message if this happens.
- Any non-discovery step requires a valid `<DOC_ROOT>/.progress.json` with `version: 2` and a persisted `manifest`.
- If the saved manifest is missing, invalid, or v1-only, abort and tell the user to run `/document-systems --force` once to initialize.

## Mode

Two modes, decided at initialization and recorded in `.progress.json` as `"mode"`:

- **multi** (default, no flag): the multi-subsystem flow — Discovery → root 系统总览 → per-subsystem `§1–§10` docs → review. This is the flow documented in Phases 1–6 below.
- **single** (`--single`): the current folder is ONE system — a single `§1–§10` document at `<DOC_ROOT>/architecture.md`, with no Discovery, no root overview, and no subsystem subdirs. Phase 1.2 resolves the mode; the single-mode deltas to the flow below are collected in **## Single mode overrides**.

## Hard Constraints (apply to main agent AND all subagents)

Before any action, main agent and all subagents must read `references/wiki-principles.md` and `references/code-wiki-conventions.md`. All rules in those files apply, in addition to the rules below.

You MUST NOT:
- Modify any file or git state in the SOURCE repo; this skill only writes under `<DOC_ROOT>`, the wiki `.gitignore` (in `<DOC_GIT_ROOT>`), and the engine-maintained `<WIKI_BASE>/<DOMAIN>/index.md` (domain index) + `<WIKI_BASE>/.wiki.json` (domain registry)
- Read `node_modules/`, `target/`, `dist/`, `build/`, `.git/`, `.idea/`, `.vscode/`, `out/`, or any compiled artifact (`*.class`, `*.jar`, `*.pyc`, lock files)
- Run Discovery/topology during the default path; only `--force` or explicit `--step=discovery` may do that
- Skip requested steps or reorder them; requested steps always execute in canonical order: discovery → root → subsystems → review (multi mode), or doc → review (single mode)
- Let subagents do scheduling — only the main agent decides ordering
- Translate code identifiers, Bean names, table names, topic names, config keys, error codes (preserve them in original form)

You MUST:
- Pause and confirm with the user before proceeding when `git status` is dirty
- Treat existing generated docs and legacy `*/doc/architecture.md` / `README.md` as **hints about author intent**, NEVER as authoritative — verify against code before incorporating
- Rewrite target `architecture.md` files using the CURRENT `document-systems` prompts/templates, so document structure changes in this skill are applied during refresh

---

## Phase 1 — Preparation (main agent)

### 1.0 Resolve documentation location (run before any git check or write)

Generated docs live OUTSIDE the source repo, in a per-repo subfolder under a configurable wiki base. Resolve the location once, here, and reuse it everywhere below.

1. **Determine `WIKI_BASE`**:
   - Read the shared config `%USERPROFILE%\.document-systems.json` (e.g. `C:\Users\admin\.document-systems.json`). If it exists with a non-empty `wiki_base` and `--reconfigure` is NOT set, use that value.
   - Otherwise (config missing/empty, or `--reconfigure`) run the first-run question below, then persist.
2. **First-run question** — ask the user where docs should be stored. In Claude Code use the `AskUserQuestion` tool; if that tool is unavailable (other harness), print the options and wait for a typed reply.
   - Question (Chinese): 「架构文档要保存到哪个 wiki 根目录？将在其下按仓库名建子目录。」
   - Options: `D:\wiki（默认，推荐）` and `自定义路径`. A custom absolute path is taken from the user's free-text ("Other") reply; the default option means `D:\wiki`.
   - Persist the result: write `{"wiki_base": "<chosen absolute path>"}` to `%USERPROFILE%\.document-systems.json`.
3. **Derive the path set** (used by every later phase; the literal `document/` is no longer used):
   - `REPO_ROOT` = output of `git rev-parse --show-toplevel` when inside a git work tree, else the current directory.
   - `REPO_NAME` = the basename of `REPO_ROOT`.
   - `DOMAIN` = resolved in step 3b below. The wiki is split into 领域 / domains (e.g. `old_project`, `fms`), each holding its own repos. **Domains are mandatory — there is no flat layout.**
   - `DOC_ROOT` = `<WIKI_BASE>/<DOMAIN>/<REPO_NAME>` — absolute folder holding this repo's docs.
   - `DOC_GIT_ROOT` = `<WIKI_BASE>` — the git work tree that owns the docs.
   - `DOC_REL` = `<DOMAIN>/<REPO_NAME>` — the pathspec after `--` in every git command.

3b. **Resolve `DOMAIN`** (deterministic engine subcommand + skill-side prompting). `<ENGINE_CLI>` = `<this skill's install dir>/scripts/wiki_engine/cli.py` (document-systems IS the engine's install root). Run:

```
python -X utf8 <ENGINE_CLI> resolve-domain --repo <REPO_ROOT> --wiki <WIKI_BASE>
```

   Parse the single JSON object printed:
   - `{"status":"resolved","domain":<D>}` → `DOMAIN = <D>` (auto-resolved from `.wiki.json` or the repo's parent folder; the engine persists the mapping in `<WIKI_BASE>/.wiki.json`).
   - `{"status":"no_registry","candidate":<C>}` → first-time setup. `AskUserQuestion`: 「未发现域配置。以父目录名 `<C>` 建立首个域并归入本仓？」 options 「是，建域 `<C>`（推荐）」/「自定义域名」. With the chosen `<d>`, run `python -X utf8 <ENGINE_CLI> resolve-domain --repo <REPO_ROOT> --wiki <WIKI_BASE> --set <d>`; `DOMAIN = <d>`.
   - non-zero exit `{"code":"E_UNKNOWN_DOMAIN","detail":{"candidate":<C>,"domains":[...]}}` → the parent `<C>` is not a known domain. `AskUserQuestion`: pick one of the existing `domains`, OR register `<C>` as a **new** domain. If the user picks "new domain `<C>`", ask a SECOND confirmation 「确认把 `<C>` 加入 domains 白名单？」 before persisting; then `resolve-domain … --set <chosen>`; `DOMAIN = <chosen>`. **No "keep this repo flat" option** — domains are mandatory.
   - If the user declines to establish/choose a domain, ABORT this run with a clear Chinese message (never silently fall back to a flat path).
4. **Ensure the wiki base is a git repo** (the diff/restore review workflow depends on it):
   - Create `<WIKI_BASE>` if it does not exist.
   - Run `git -C <WIKI_BASE> rev-parse --is-inside-work-tree`. If it fails, run `git -C <WIKI_BASE> init` and print:

```text
ℹ️ 已在 <WIKI_BASE> 初始化 git 仓库，用于对比与回滚生成的文档。
```

5. **Name-collision guard**: if `<DOC_ROOT>` already exists and clearly belongs to a different source repo, warn the user and let them continue or abort (running `--reconfigure` is the way to switch to a different wiki base).

### 1.1 Wiki git status check

This skill relies on `git diff` (or IDE line-level diff) so the user can compare previously generated docs with the new ones; git is a hard dependency — but the dependency is on the **wiki repo** (`<DOC_GIT_ROOT>`) ensured in 1.0, NOT on the documented source repo. The source repo does NOT need to be a git repo (this skill never writes to source). Run the following checks in order; whenever a step requires user input, wait for it before continuing.

**1.1.a `<DOC_ROOT>` gitignore check**

Run `git -C <DOC_GIT_ROOT> check-ignore -q <DOC_REL>/`. If ignored (exit code 0), print:

```text
⚠️ `<DOC_ROOT>` 在 wiki 仓库的 `.gitignore` 中。
覆盖后无法使用 `git diff` 与历史版本对比，且 commit 历史不会留下生成结果。
建议先把它从 `.gitignore` 移除（或改成只忽略 `<DOC_REL>/.review.md` 等运行产物）后再运行。

请输入：
  C  继续（接受不可对比的代价）
  A  中止
```

Accept only `C` to continue; otherwise abort.

**1.1.b `<DOC_ROOT>` path status**

Run `git -C <DOC_GIT_ROOT> status --porcelain -- <DOC_REL>/`. If there are tracked uncommitted changes, print:

```text
⚠️ `<DOC_ROOT>` 中存在未提交改动。
本次生成将覆盖现有文档。如希望生成后用 `git -C <DOC_GIT_ROOT> diff HEAD -- <DOC_REL>/` 对比新旧，
请先在 wiki 仓库 commit 或 stash 当前改动；否则旧版本将无法找回。

请输入：
  C  继续覆盖（放弃当前未提交改动的对比能力）
  S  我已 commit/stash，继续
  A  中止
```

Both `C` and `S` proceed (the user has been warned); otherwise abort.

### 1.2 Resolve mode and select steps

Do this before any document writes.

**Step 0 — resolve mode.** Read `<DOC_ROOT>/.progress.json` for a saved `"mode"`, then apply:

| Condition | Mode |
|---|---|
| `--single` present | **single** — if a multi `.progress.json` already exists, warn and confirm before overwriting (see **## Single mode overrides**) |
| no `--single`, saved `"mode": "single"` | **single** |
| no `--single`, saved `"mode": "multi"` / `"mode"` key absent / no `.progress.json` | **multi** |

If mode resolves to **single**, do NOT use Step 1 below — take step selection (and the single-mode `--step` / invalid-flag rules) from **## Single mode overrides** instead, where the progress shape and the Phase 2–6 deltas also live; Step 1's multi `--force` expansion and `--no-discovery` modifier do not apply in single mode. The rest of this section covers **multi**.

**Step 1 — select steps (multi):**

| Input | Selected steps |
|---|---|
| no `--step`, no `--force` | `subsystems, review` |
| no `--step`, with `--force` | `discovery, root, subsystems, review` |
| `--step=all` | `discovery, root, subsystems, review` |
| `--step=<list>` | the listed steps |
| `--no-discovery` (modifier) | remove `discovery` from the selection |

Then sort the selected steps into canonical order: `discovery`, `root`, `subsystems`, `review`.

**Invalid combinations (multi)** — print a concise Chinese message and produce no side effects:

- `--force` with `--only`
- `--force` with `--no-discovery`
- `--force` with a narrow explicit `--step` other than `all`
- `--only` without `subsystems` in the selected steps

### 1.3 Create output directory

If `<DOC_ROOT>` does not exist, create it (`<WIKI_BASE>` itself was ensured in 1.0).

### 1.4 Update .gitignore

Read `<DOC_GIT_ROOT>/.gitignore` (create if missing).

- If a prior run added a `<DOC_REL>/.progress.json` line, REMOVE it — `.progress.json` is now tracked on purpose (see below).
- If `<DOC_REL>/.review.md` is not present as a line, append:

```text
# /document-systems regenerable run report
<DOC_REL>/.review.md
```

`<DOC_REL>/.progress.json` is committed on purpose: it carries the resolved `mode`, the discovered `manifest`, and `topology` that other maintainers (and fresh clones) need to refresh docs without re-running Discovery — and it is the ONLY machine record that a single-mode repo is single. It changes every run (timestamps / statuses), so commit it alongside the docs.

### 1.5 Read global context

Read up to these files only (skip if missing, total budget < 50KB):

- Repo root `CLAUDE.md`
- Repo root `README.md` / `README` / `README.MD`
- Repo root `pom.xml` / `package.json` / `pyproject.toml` (top-level only)

Note module declarations, conventions, naming patterns. Hold this in working memory for root generation and dispatch prompts.

### 1.6 Load or initialize progress

If `discovery` is selected:

- Ignore any previous manifest for discovery purposes.
- Start a fresh in-memory progress object with `version: 2` and `mode: "multi"`.
- Discovery in Phase 2 will populate `manifest`, `topology`, and subsystem statuses.

If `discovery` is NOT selected:

- Read `<DOC_ROOT>/.progress.json`.
- Require `version: 2`, a `manifest.subsystems` array, and `topology` layers.
- Abort if missing/invalid with:

```text
⚠️ 未找到可复用的 v2 子系统清单。
默认更新不会重新执行 Discovery/拓扑。请先运行：
  /document-systems --force
完成初始化后，再使用默认命令或 `--only=<子系统名>` 做日常更新。
```

When loading succeeds, print one-line summary:

```text
已加载子系统清单：<N> 个子系统，<L> 个拓扑层；本次步骤：<steps>
```

---

## Phase 2 — Discovery/topology (only when selected)

Skip this phase unless selected steps include `discovery`.

Dispatch a single Explore subagent with `model: opus`.

**Subagent prompt**: read `references/discovery-prompt.md`, substitute `<REPO_ROOT>` with the absolute repo root path, and pass the resulting string as the subagent's prompt.

### After discovery returns

1. **Validate**: parse the JSON. On parse failure, dispatch the same subagent ONCE more with a stricter preamble (`Your previous output was not valid JSON. Return ONLY a valid JSON object matching the schema. No prose, no markdown.`). On second failure, abort with error message to user.
2. **Topological sort**: order subsystems so all `deps` precede their dependents. Detect cycles:
   - On cycle: pick the edge with the smallest weight (heuristic: edge involving a `java-lib` first, then alphabetically) and remove it. Log: `⚠️ 发现循环依赖 <A> ↔ <B>，已临时切断 <A → B> 边以继续；最终文档需人工核实。`
   - Group into layers L0, L1, L2, ... where Lk contains nodes whose deps are all in L0..Lk-1.
3. **Persist v2 progress** to `<DOC_ROOT>/.progress.json`:
   - Save the full discovery JSON under `manifest`.
   - Save topology layers under `topology`.
   - Initialize every subsystem status to `pending`.
   - Set `started_at` and `updated_at` timestamps.

---

## Phase 3 — Root architecture.md (only when selected)

Skip this phase unless selected steps include `root`.

Read `references/templates/root-architecture.md`. The leading HTML comment in that file defines every placeholder and its derivation rule. Apply substitutions from the saved/in-memory v2 manifest and topology, remove the leading comment block, and write the result to `<DOC_ROOT>/architecture.md`.

Root generation NEVER performs Discovery by itself. If manifest data is stale, the user must run `/document-systems --force` or `--step=discovery,root`.

Encoding safety for root generation:

- Write `<DOC_ROOT>/architecture.md` as UTF-8 from `references/templates/root-architecture.md`; do not hand-compose large non-ASCII root content in shell command strings.
- On Windows, do NOT pass non-ASCII root document content or generator scripts through PowerShell here-string/stdin pipelines such as `@'...'@ | python -`; this can replace CJK text with `?` before Python receives it.
- If a helper script is needed, write/read it as a UTF-8 file or keep the shell-delivered script ASCII-only and load all non-ASCII text from UTF-8 files / escaped code points.
- After writing the root document, self-check that the leading template comment is gone, no `<PLACEHOLDER>` tokens remain, no garbled question-mark runs such as `???` / `????` exist, and the expected fixed headings from the template are present.
- Remove the leading HTML comment by matching a standalone comment terminator line (`^-->`), not by splitting on the first `-->`; the template comment contains Mermaid edge examples such as `A --> B`.


---

## Phase 4 — Per-subsystem analysis (only when selected)

Run this phase when selected steps include `subsystems`; otherwise skip.

### 4.1 Select targets

Build the subsystem target set from the loaded v2 manifest:

- With `--only=<name>`: target exactly that subsystem. If not found, abort with `⚠️ 子系统 <name> 不在已保存清单中，请检查名称或先运行 /document-systems --force。`
- Without `--only`: target all subsystems in topology order.

For every target, the dispatcher must pass both:

- `<EXISTING_OLD_DOC>`: legacy `<subsystem>/doc/architecture.md` if any, else `null`.
- `<EXISTING_GENERATED_DOC>`: current `<DOC_ROOT>/<NAME>/architecture.md` if any, else `null`.

The target document is rewritten from the current `references/subsystem-prompt.md` structure. Existing generated docs are hints only; they do not define the output structure.

### 4.2 Scheduling loop

The main agent processes layers L0, L1, L2, ... in order. Within each layer, all selected targets are dispatched in parallel via a SINGLE message containing multiple Task tool calls. After each layer completes, `progress.json` is updated and the next layer starts.

Skip/resume behavior:

- If `discovery` ran in this invocation, every target starts as `pending`.
- If `--only` is present, process the target even if its saved status is `done`; this is an explicit refresh.
- If no `--only` and no `--force`, process all selected subsystems, including `done`; default refresh intentionally rewrites docs using the current skill contract.
- `in-progress` is treated as crashed mid-run and retried.
- `failed` is retried once.

Algorithm (illustrative — execute the equivalent in your own reasoning, this is not literal code to run):

```python
selected = all_manifest_subsystems() if only is None else [manifest_subsystem(only)]
for layer_idx, layer in enumerate(topology_layers):
    pending = [s for s in layer if s.name in selected]
    if not pending:
        continue

    for s in pending:
        progress.statuses[s.name] = 'in-progress'
    save_progress_json()

    results = parallel_dispatch([
        Task(
            subagent_type='general-purpose',
            model='sonnet',
            prompt=build_subsystem_prompt(s, upstream_docs=[
                f'{DOC_ROOT}/{dep}/architecture.md' for dep in s.deps
            ]),
        )
        for s in pending
    ])

    for s, result in zip(pending, results):
        if result.ok:
            progress.statuses[s.name] = 'done'
        else:
            retry = Task(..., model='sonnet')
            progress.statuses[s.name] = 'done' if retry.ok else 'failed'

    save_progress_json()
```

**The "single message, multiple Task calls" requirement is non-negotiable.** That is what makes same-layer subagents truly parallel and respects the layered ordering.

### 4.3 Subsystem subagent prompt

Read `references/subsystem-prompt.md` and substitute these placeholders for each subsystem before dispatching:

- `<NAME>` — subsystem name
- `<ABSOLUTE_PATH>` — absolute filesystem path to the subsystem directory
- `<TYPE>` — one of: java-service, java-lib, frontend, node-service, python-service
- `<UPSTREAM_DOCS>` — list of absolute paths to already-generated upstream architecture.md files (one per dep from topology)
- `<EXISTING_OLD_DOC>` — path to legacy `<subsystem>/doc/architecture.md` if any, else `null`
- `<EXISTING_GENERATED_DOC>` — path to current generated `<DOC_ROOT>/<NAME>/architecture.md` if any, else `null`
- `<DISCOVERY_HINTS>` — JSON hints object for this subsystem from the saved manifest
- `<REPO_ROOT>` — repository root absolute path
- `<DOC_ROOT>` — absolute folder holding this repo's generated docs (`<WIKI_BASE>/<REPO_NAME>`); the subagent writes to `<DOC_ROOT>/<NAME>/architecture.md`
- `<SINGLE_MODE>` — `false` in multi mode (the single-mode dispatch in **## Single mode overrides** sets it `true`)

The subagent's output document structure (§1–§10) is defined inside `references/subsystem-prompt.md` and must be followed exactly.

---

## Phase 5 — Cross-document review (only when selected)

Skip this phase unless selected steps include `review`.

Dispatch one general-purpose subagent with `model: opus`.

**Subagent prompt**: read `references/review-prompt.md`, substitute `<REPO_ROOT>`, `<DOC_ROOT>`, and `<SINGLE_MODE>` (`true` in single mode), and pass the resulting string as the subagent's prompt.

After the review subagent returns, the main agent:
- Reads `<DOC_ROOT>/.review.md`
- For minor issues affecting only the root doc → applies fixes inline only if `root` was selected in this invocation; otherwise leaves the issue in `.review.md`
- For issues requiring per-subsystem edits → leaves them in `.review.md` for user follow-up
- Prints a brief Chinese summary of the report to the user

---

## Phase 6 — Wrap-up (main agent prints to user)

**Refresh the domain index first** (so the domain landing page reflects this repo): run `python -X utf8 <ENGINE_CLI> update-domain-index --wiki <WIKI_BASE> --domain <DOMAIN>`. Skip only when no docs were (re)generated (e.g. a pure `--step=review` run).

Print:

```text
✅ 文档更新完成
仓库：<REPO_NAME>
文档位置：<DOC_ROOT>
本次步骤：<STEPS>
处理子系统：<DONE_COUNT>/<TARGET_COUNT>
失败：<FAILED_LIST 或 "无">

产物：
  <DOC_ROOT>/architecture.md             — 系统总览（仅在 root 步骤执行时更新）
  <DOC_ROOT>/<name1>/architecture.md     — <name1> 详细
  <DOC_ROOT>/<name2>/architecture.md     — <name2> 详细
  ...
  <DOC_ROOT>/.review.md                  — 跨文档审校报告（仅在 review 步骤执行时更新）
  <WIKI_BASE>/<DOMAIN>/index.md          — 域索引（本域各仓导航；每次生成后自动刷新）

查看待确认疑问（每个子系统文档的 §10）：
  在 IDE 中全局搜索 `## 10. 待确认`
  Unix / Git Bash / WSL：grep -rnF "## 10. 待确认" <DOC_ROOT>
  PowerShell：          Select-String -Pattern '## 10\. 待确认' -Path <DOC_ROOT> -Recurse

对比本次更新的差异：
  git -C <DOC_GIT_ROOT> diff HEAD -- <DOC_REL>/                                   # 全部文档
  git -C <DOC_GIT_ROOT> diff HEAD -- <DOC_REL>/<name>/architecture.md             # 单个子系统
还原某个子系统的上一版：
  git -C <DOC_GIT_ROOT> restore --source=HEAD -- <DOC_REL>/<name>/architecture.md

下次使用：
  /document-systems                         # 基于已保存清单，更新全部子系统并审校
  /document-systems --only=<name>           # 基于已保存清单，仅更新某子系统并审校
  /document-systems --force                 # 重新 Discovery/拓扑并全量重生成
  /document-systems --step=root             # 只基于已保存清单重写系统总览
  /document-systems --step=review           # 只重新审校现有文档
  /document-systems --step=all --no-discovery # 跳过 Discovery，重写 root + 子系统 + review
```

Single mode prints a different message — see **## Single mode overrides**.

---

## Single mode overrides

When Phase 1.2 resolves **mode = single** (via `--single`, or a saved `"mode": "single"`), the current folder is documented as ONE system. Follow the Phase 1–6 flow above with the deltas below; everything not listed here is unchanged. Canonical step order is `doc`, `review`.

**Domain resolution + domain index apply unchanged**: a single-system repo still resolves `DOMAIN` (Phase 1.0 step 3b) → `DOC_ROOT = <WIKI_BASE>/<DOMAIN>/<REPO_NAME>`, and Phase 6 still refreshes `<WIKI_BASE>/<DOMAIN>/index.md` (the repo is one of the domain's repos).

**Initialization.** `--single` (with or without `--force`) initializes/uses single mode. If a multi `.progress.json` already exists, `--single` re-initializes as single — warn and confirm before overwriting. If the user declines, abort with no changes — keep the existing multi `.progress.json` and docs intact (e.g. print `已取消：保留现有 multi 文档，未做改动。`). With a saved `"mode": "single"`, `--force` (even without `--single`) re-initializes in single mode — re-infer `<TYPE>`, start a fresh single progress, and regenerate the doc; it never switches to multi, and steps remain `doc, review`.

**Step selection (replaces Phase 1.2 Step 1).** The multi-only step names `discovery` / `root` / `subsystems` and the flags `--only` / `--no-discovery` are invalid in single mode → abort with a concise Chinese message and no side effects. Otherwise:

| Input | Selected steps |
|---|---|
| no `--step` | `doc, review` |
| `--step=all` | `doc, review` |
| `--step=<list>` (from `doc`, `review`) | the listed steps |

Sort into canonical order: `doc`, `review`.

**Phase 1.5 — type inference (added).** Also infer the system `<TYPE>` from the root manifest files using the **Detection rules** table in `references/discovery-prompt.md`. If ambiguous, pick the closest match and note it.

**Phase 1.6 — progress (replaces the multi manifest/topology load):**

- On init (`--single`): start a fresh in-memory progress `{ "version": 2, "mode": "single", "system": { "name": <REPO_NAME>, "type": <inferred TYPE>, "path": "." }, "status": "pending" }`; persist after Phase 4.
- On a default single run (mode came from saved progress): read `<DOC_ROOT>/.progress.json`, require `mode: "single"` and a `system` object. If `<DOC_ROOT>/architecture.md` is missing, treat it as init and regenerate. The multi "require manifest/topology" check does NOT apply.
- Print: `已加载单系统进度：<system.name>（<system.type>）；本次步骤：<steps>`.

**Phase 2 & Phase 3 — skipped.** Single mode has no Discovery (the `<TYPE>` was inferred in Phase 1.5) and no root 系统总览 overview; the single `§1–§10` document is produced in Phase 4 instead.

**Phase 4 — single dispatch (replaces 4.1–4.3).** Skip topology and the scheduling loop. Dispatch ONE subsystem subagent (`model: sonnet`) with `<SINGLE_MODE> = true` and:

- `<NAME>` = `<REPO_NAME>`; `<ABSOLUTE_PATH>` = `<REPO_ROOT>`; `<TYPE>` = the type inferred in Phase 1.5.
- `<UPSTREAM_DOCS>` = none; `<DISCOVERY_HINTS>` = none.
- `<EXISTING_OLD_DOC>` = legacy root `doc/architecture.md` / `README.md` if any, else `null`.
- `<EXISTING_GENERATED_DOC>` = `<DOC_ROOT>/architecture.md` if present, else `null`.
- `<REPO_ROOT>` and `<DOC_ROOT>` as resolved in Phase 1.

The subagent writes `<DOC_ROOT>/architecture.md` (per **Single-system mode** in `references/subsystem-prompt.md`). Set `progress.status = "in-progress"` before dispatch, then `"done"` / `"failed"` after (retry once on failure); persist `.progress.json`. Continue to Phase 5 when `review` is selected.

**Phase 5 — review.** There is exactly one document, so the root-vs-subsystem distinction does not apply: leave all findings in `.review.md` for the user and print the summary. (`<SINGLE_MODE> = true` is substituted into `references/review-prompt.md` as noted in Phase 5.)

**Phase 6 — wrap-up message** (replaces the multi message):

```text
✅ 单系统文档更新完成
仓库：<REPO_NAME>
文档位置：<DOC_ROOT>/architecture.md
本次步骤：<STEPS>
状态：<done | failed>

查看待确认疑问（§10）：
  在 IDE 中全局搜索 `## 10. 待确认`
  PowerShell：Select-String -Pattern '## 10\. 待确认' -Path <DOC_ROOT>\architecture.md

对比本次更新的差异：
  git -C <DOC_GIT_ROOT> diff HEAD -- <DOC_REL>/architecture.md
还原上一版：
  git -C <DOC_GIT_ROOT> restore --source=HEAD -- <DOC_REL>/architecture.md

下次使用：
  /document-systems                 # 复用单系统模式，刷新该文档并审校
  /document-systems --step=review   # 只重新审校
```

**Progress file shape** (replaces the multi `manifest` / `topology` shape):

```json
{
  "version": 2,
  "mode": "single",
  "started_at": "2026-05-29T10:00:00+08:00",
  "updated_at": "2026-05-29T10:05:00+08:00",
  "system": { "name": "my-service", "type": "java-service", "path": "." },
  "status": "done",
  "last_run": { "steps": ["doc", "review"] }
}
```

**Error recovery (single-mode rows):**

| Failure | Action |
|---|---|
| `--single` over an existing multi `.progress.json` | Warn and confirm before re-initializing as single; on decline, abort with no changes |
| Missing single-system doc on a default single run | Treat as init and regenerate `<DOC_ROOT>/architecture.md` |
| `--only` / `--no-discovery` / `discovery` / `root` / `subsystems` used in single mode | Abort with a Chinese message (not valid in single mode) |

---

## Progress file schema

Path: `<DOC_ROOT>/.progress.json`

```json
{
  "version": 2,
  "mode": "multi",
  "started_at": "2026-05-13T10:00:00+08:00",
  "updated_at": "2026-05-13T10:15:00+08:00",
  "manifest": {
    "subsystems": [
      {
        "name": "port-data",
        "type": "java-service",
        "path": "port-data",
        "deps": ["port-service", "port-auth"],
        "hints": {
          "ports": ["17004"],
          "outbound": ["feign:port-auth", "kafka:tide-bridge"],
          "existing_doc": "port-data/doc/architecture.md",
          "tech": ["spring-boot", "mybatis-plus"]
        }
      }
    ],
    "resources": [{"name": "middleware", "purpose": "Docker startup scripts for ES/MySQL/Nacos"}],
    "warnings": []
  },
  "topology": [
    ["port-service"],
    ["port-auth", "port-event"],
    ["port-data", "port-admin"]
  ],
  "statuses": {
    "port-service": "done",
    "port-auth": "done",
    "port-data": "in-progress",
    "port-admin": "pending",
    "port-foo": "failed"
  },
  "last_run": {
    "steps": ["subsystems", "review"],
    "only": null
  }
}
```

Single mode uses a lighter shape (no `manifest` / `topology`) — see **## Single mode overrides**.

Status rules:
- `done` → still refresh during default `subsystems`; skip only when a future flow explicitly says to resume unfinished work
- `in-progress` → treat as crashed mid-run, retry
- `failed` → retry once
- `pending` or absent → process normally

---

## Error recovery

| Failure | Action |
|---|---|
| Missing v2 manifest on non-discovery run | Abort and tell user to run `/document-systems --force` |
| Discovery JSON invalid | Retry once with stricter prompt; abort to user if still bad |
| Subsystem in `--only` not found | Abort and tell user to check name or run `/document-systems --force` |
| Subsystem subagent crash / timeout | Retry once; on second fail mark `failed` and continue rest |
| Topology cycle detected | Cut lowest-weight edge, log warning, continue |
| Disk write error | Abort cleanly, preserve `progress.json` for resume |
| User aborts at Phase 1 | Exit cleanly with no side effects |

Single-mode failure rows are listed in **## Single mode overrides**.

---

## What this skill does NOT do

Out of scope (user should use other tools):
- Code quality review
- Security audit
- Performance/profiling analysis
- Test coverage report

This skill does not generate derived files for change tracking, question aggregation, asset indexing, or history review. Use native tools: `git diff` / `grep` / IDE global search / `git restore` (wiki-principles §7).

This skill produces *descriptive* architecture documentation only.
