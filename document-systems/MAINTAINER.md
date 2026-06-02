# Maintainer Checks

Static checks for the `document-systems` and `wiki-refine` skill files. Run these before declaring a change to the skill done.

These checks verify the **skill implementation** itself, not the docs the skill produces. Output validation for a *user's* skill run is handled by `references/review-prompt.md`, which both skills dispatch at the end of their flow.

Files in scope:

- `references/wiki-principles.md`
- `references/code-wiki-conventions.md`
- `references/subsystem-prompt.md`
- `references/review-prompt.md`
- `references/discovery-prompt.md`
- `references/templates/root-architecture.md`
- `SKILL.md`
- `../wiki-refine/SKILL.md`
- `../wiki-refine/references/refine-subagent-prompt.md`

---

## 1. Rule-set completeness

After splitting or moving rules between files, the total rule set must not shrink. For each rule in the pre-change files, confirm its post-change location (either a shared file or a skill-local prompt). No rule may silently disappear.

## 2. Shared-contract independence

- `references/wiki-principles.md` rule descriptions must NOT contain code-wiki-specific terminology (subsystem, source code, data channel, grep, etc.). Examples may demonstrate code-wiki content (the current ecosystem), but the rules themselves must stay domain-neutral.
- `references/code-wiki-conventions.md` must be readable on its own — do not assume the reader has read `wiki-principles.md`. Do not duplicate clauses already in `wiki-principles.md`.
- The two files have no read-order dependency; either can be loaded first.

## 3. Absolute reference paths from wiki-refine

`../wiki-refine/SKILL.md` and `../wiki-refine/references/refine-subagent-prompt.md` reference `wiki-principles.md` and `code-wiki-conventions.md` only by absolute path. The skill must abort with a clear Chinese message if either file is missing at runtime.

## 4. Section-name alignment

Section names referenced in `refine-subagent-prompt.md`'s `root_suggestions.target` field — root-document chapters and subsystem §1–§10 — must match exactly across:

- `references/subsystem-prompt.md` (Output template chapter list)
- `references/templates/root-architecture.md` (root template chapter list)
- `references/review-prompt.md` (Check 1 chapter list)
- `references/wiki-principles.md` (§5 §10 format example)
- `references/code-wiki-conventions.md` (§4 / §6 / §7 section structure references)

Renaming any section requires updating all referencing files together.

## 5. Skill-prompt language convention

- Agent-facing prose (rules, process steps, self-review checklists, hard constraints, phase descriptions) in **English**.
- User-facing prose (printed messages, output templates, generated wiki content, review reports) in **Chinese**.
- Examples in shared / principle files stay in whatever language demonstrates the target wiki content (Chinese for the current ecosystem).
- Chapter names in output templates stay Chinese — they are the literal content the agent writes.

## 6. No meta-categorization in agent-facing prompts

Skill prompts presented to the agent list rules directly, without meta-categorization labels such as `(共享契约)`, `(document-systems 专属)`, `(specific to X)`, `(general to wikis)`. The opening of each prompt file says "Before starting, read X and Y" — that is sufficient to establish the dependency. Maintenance-level distinctions belong in this file, not in the agent prompt.

## 7. Documentation-location resolution

Output no longer lives at a fixed `document/`; it resolves to `<DOC_ROOT>` = `<WIKI_BASE>/<REPO_NAME>` (default `WIKI_BASE` = `D:\wiki`), with git operations scoped to the wiki repo via `git -C <DOC_GIT_ROOT> ... -- <DOC_REL>/`.

- Both `SKILL.md` files MUST define `WIKI_BASE`, `REPO_ROOT`, `REPO_NAME`, `DOC_ROOT`, `DOC_GIT_ROOT`, `DOC_REL` in a Phase 1.0 step that runs before any git check or file write/read.
- `<DOC_ROOT>` (and, where git commands are emitted, `<DOC_GIT_ROOT>` / `<DOC_REL>`) must be the ONLY way output paths are expressed in `subsystem-prompt.md`, `review-prompt.md`, `refine-subagent-prompt.md`, and `templates/root-architecture.md`. No literal `document/` output path may remain — the only allowed `document/` mentions are explanatory notes and the neutral `<doc-dir>` examples in `wiki-principles.md`.
- Every `<DOC_ROOT>` used by a prompt template must appear in that template's Inputs list (the dispatcher substitutes it).
- `discovery-prompt.md` stays output-agnostic: it emits only source paths relative to `<REPO_ROOT>` and must NOT reference `<DOC_ROOT>`.
- Inter-document links inside generated docs stay relative (`./<name>/architecture.md`, `../architecture.md`, `<子系统>/architecture.md`) so they remain valid wherever `<DOC_ROOT>` resolves. Operational hints embedded in generated content (grep / git commands) carry the `<DOC_ROOT>` / `<DOC_GIT_ROOT>` / `<DOC_REL>` placeholders and are substituted at write time.
- The wiki repo TRACKS `<DOC_REL>/.progress.json` (committed, NOT gitignored); only `<DOC_REL>/.review.md` (a regenerable report) is ignored. The committed `.progress.json` is the only machine record of `mode` / `manifest` / `topology` for other maintainers and fresh clones, so Phase 1.4 must NOT add `.progress.json` to `.gitignore` and must strip a legacy `.progress.json` ignore line.

## 8. Shared-config contract between the two skills

Both skills read/write one shared config `%USERPROFILE%\.document-systems.json` (`{"wiki_base": "<abs path>"}`):

- First run (config absent / empty / `--reconfigure`) asks via `AskUserQuestion` (Claude Code) or a printed prompt (other harness), then persists the choice.
- `/wiki-refine` must resolve the SAME `DOC_ROOT` that `/document-systems` wrote to (same config key, same `<WIKI_BASE>/<REPO_NAME>` rule). A change to the resolution rule in one skill must be mirrored in the other.

## 9. Single vs multi mode parity

`/document-systems --single` documents a one-system repo as a single `§1–§10` doc at `<DOC_ROOT>/architecture.md`; default (no flag) is multi. The mode is recorded in `.progress.json` as `"mode"` and reused on later runs.

**Structure (Shape 1).** In each `SKILL.md`, the single/multi divergence lives in exactly ONE `## Single mode overrides` block — mirroring the `## Single-system mode` delta block already used by `subsystem-prompt.md` and `refine-subagent-prompt.md`. The Phase 1–6 body is the multi flow, with NO inline `if single / if multi` branching, except the single fork pointer at the mode-resolution step (document-systems Phase 1.2, wiki-refine Phase 1.3). Mechanical check: every phase the multi flow runs that single changes or skips must have a matching entry in the overrides block, and no single-specific instruction may remain inline in the multi flow. (Brief `see ## Single mode overrides` cross-references and the Phase 1.2 / 1.3 fork pointer are fine — what is forbidden is executable single-mode logic interleaved into the multi phases.)

**Mode resolution (both skills).** Single ONLY when `--single` is passed (document-systems) or the saved `"mode"` is `"single"`; absent key, absent file, or `"mode": "multi"` all default to multi. A v2 `.progress.json` without `"mode"` is treated as multi (back-compat).

**document-systems `## Single mode overrides` must cover:** step selection (`doc`, `review` only; `discovery` / `root` / `subsystems` / `--no-discovery` / `--only` abort in single); Phase 1.5 type inference; Phase 1.6 progress shape (`system` + `status`); Phase 2 & 3 skipped (no Discovery, no root overview, no subsystem subdirs); Phase 4 single dispatch (one subagent, `<SINGLE_MODE> = true`, writes `<DOC_ROOT>/architecture.md`); Phase 5 single review handling; Phase 6 single wrap message; the single `.progress.json` shape; and the single-mode error rows.

**wiki-refine `## Single mode overrides` must cover:** Phase 1.3 single context (no `子系统清单`, one target); Phase 1.4 ready-line swap; Phase 2.2 single target (skip candidate matching / `--subsystem`); Phase 2.3 single dispatch (subagent edits the single doc directly — the "subagent must not edit the root doc" constraint is inverted); Phase 2.5 skipped (empty `root_suggestions`); Phase 3.2 wrap-line swaps.

**Reference prompts (unchanged by the reorg).** `subsystem-prompt.md`, `review-prompt.md`, and `refine-subagent-prompt.md` accept `<SINGLE_MODE>` and honor single mode via their own `## Single-system mode` block (edit the single doc directly, return empty `root_suggestions`, omit the parent-overview header).
