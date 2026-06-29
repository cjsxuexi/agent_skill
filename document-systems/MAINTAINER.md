# Maintainer Checks

Static checks for the `document-systems` and `wiki-refine` skill files. Run these before declaring a change to the skill done.

These checks verify the **skill implementation** itself, not the docs the skill produces. Output validation for a *user's* skill run is handled by `references/review-prompt.md`, which both skills dispatch at the end of their flow.

Files in scope:

- `references/wiki-principles.md`
- `references/code-wiki-conventions.md`
- `references/common-conventions.md`
- `references/scenario-playbook.md`
- `references/subsystem-prompt.md`
- `references/review-prompt.md`
- `references/discovery-prompt.md`
- `references/templates/root-architecture.md`
- `references/templates/common-{glossary,shared-lib,protocol,infra}.md`
- `scripts/wiki_engine/**` (the deterministic engine + its tests)
- `MIGRATION.md`
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

## 3. Install-root resolution from wiki-refine

`../wiki-refine/SKILL.md` and `../wiki-refine/references/refine-subagent-prompt.md` reference the engine CLI and the shared contract files (`wiki-principles.md`, `code-wiki-conventions.md`, `common-conventions.md`, `scenario-playbook.md`) by an absolute path that is the **expansion of a resolved install root**, not a hardcoded literal. The install root is resolved by the probe order in Check 13. The skill must abort with a clear Chinese message if the install root cannot be resolved or a required contract file is missing at runtime.

## 4. Section-name alignment

Section names referenced in the root-document update targets (`refine-subagent-prompt.md`'s `root_updates` items / the engine's `update_root` named regions) — root-document chapters and subsystem §1–§10 — must match exactly across:

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

Output no longer lives at a fixed `document/`; it resolves to:

- `<DOC_ROOT>` = `<WIKI_BASE>/<DOMAIN>/<REPO_NAME>` (default `WIKI_BASE` = `D:\wiki`)
- `<DOC_REL>` = `<DOMAIN>/<REPO_NAME>`

Git operations are scoped to the wiki repo via `git -C <DOC_GIT_ROOT> ... -- <DOC_REL>/`. A `<WIKI_BASE>/.wiki.json` **domain registry** (committed, travels with the wiki repo) records **only the domain whitelist** (`{"domains": [...]}`). `resolve-domain` derives a repo's domain from its **parent folder name** (`<WIKI scope>/<DOMAIN>/<REPO>`) and validates it against that whitelist — there is no per-repo→domain map, so two same-named repos under different domain folders never collide. (A legacy basename `repos` map is dropped on load and rewritten away on the next save.)

- Both `SKILL.md` files MUST define `WIKI_BASE`, `REPO_ROOT`, `REPO_NAME`, `DOMAIN`, `DOC_ROOT`, `DOC_GIT_ROOT`, `DOC_REL` in a Phase 1.0 step that runs before any git check or file write/read. `DOMAIN` is resolved via the `resolve-domain` subcommand (see §8).
- `<DOC_ROOT>` (and, where git commands are emitted, `<DOC_GIT_ROOT>` / `<DOC_REL>`) must be the ONLY way output paths are expressed in `subsystem-prompt.md`, `review-prompt.md`, `refine-subagent-prompt.md`, and `templates/root-architecture.md`. No literal `document/` output path may remain — the only allowed `document/` mentions are explanatory notes and the neutral `<doc-dir>` examples in `wiki-principles.md`.
- Every `<DOC_ROOT>` used by a prompt template must appear in that template's Inputs list (the dispatcher substitutes it).
- `discovery-prompt.md` stays output-agnostic: it emits only source paths relative to `<REPO_ROOT>` and must NOT reference `<DOC_ROOT>`.
- Inter-document links inside generated docs stay relative (`./<name>/architecture.md`, `../architecture.md`, `<子系统>/architecture.md`) so they remain valid wherever `<DOC_ROOT>` resolves. Operational hints embedded in generated content (grep / git commands) carry the `<DOC_ROOT>` / `<DOC_GIT_ROOT>` / `<DOC_REL>` placeholders and are substituted at write time.
- The wiki repo TRACKS `<DOC_REL>/.progress.json` (committed, NOT gitignored); only `<DOC_REL>/.review.md` (a regenerable report) is ignored. The committed `.progress.json` is the only machine record of `mode` / `manifest` / `topology` for other maintainers and fresh clones, so Phase 1.4 must NOT add `.progress.json` to `.gitignore` and must strip a legacy `.progress.json` ignore line.
- **Write boundary** (both skills): `<DOC_ROOT>` (all output files), `<DOC_REL>/.gitignore` in the wiki repo, plus engine-maintained files `<WIKI_BASE>/<DOMAIN>/index.md` (domain landing index) and `<WIKI_BASE>/.wiki.json` (domain registry). No other paths outside `<DOC_ROOT>` may be written without a matching `§8` governance rule.

## 8. Shared-config contract between the two skills

Both skills read/write one shared config `%USERPROFILE%\.document-systems.json` (`{"wiki_base": "<abs path>"}`):

- First run (config absent / empty / `--reconfigure`) asks via `AskUserQuestion` (Claude Code) or a printed prompt (other harness), then persists the choice.
- `/wiki-refine` must resolve the SAME `DOC_ROOT` that `/document-systems` wrote to (same config key, same `<WIKI_BASE>/<DOMAIN>/<REPO_NAME>` rule). A change to the resolution rule in one skill must be mirrored in the other.
- **Both skills resolve `DOMAIN` by calling the SAME engine subcommand `resolve-domain`** (deterministic), with skill-side `AskUserQuestion` prompting when interactive input is needed. This single shared code path guarantees domain resolution never drifts between the two skills — a change to the algorithm is made once in the engine and both skills inherit it automatically. Domains are **mandatory**: there is no flat-mode fallback. A skill run that cannot resolve a domain MUST abort with a clear message rather than silently omitting the `<DOMAIN>` segment.

## 9. Single vs multi mode parity

`/document-systems --single` documents a one-system repo as a single `§1–§10` doc at `<DOC_ROOT>/architecture.md`; default (no flag) is multi. The mode is recorded in `.progress.json` as `"mode"` and reused on later runs.

**Structure (Shape 1).** In each `SKILL.md`, the single/multi divergence lives in exactly ONE `## Single mode overrides` block — mirroring the `## Single-system mode` delta block already used by `subsystem-prompt.md` and `refine-subagent-prompt.md`. The Phase 1–6 body is the multi flow, with NO inline `if single / if multi` branching, except the single fork pointer at the mode-resolution step (document-systems Phase 1.2, wiki-refine Phase 1.3). Mechanical check: every phase the multi flow runs that single changes or skips must have a matching entry in the overrides block, and no single-specific instruction may remain inline in the multi flow. (Brief `see ## Single mode overrides` cross-references and the Phase 1.2 / 1.3 fork pointer are fine — what is forbidden is executable single-mode logic interleaved into the multi phases.)

**Mode resolution (both skills).** Single ONLY when `--single` is passed (document-systems) or the saved `"mode"` is `"single"`; absent key, absent file, or `"mode": "multi"` all default to multi. A v2 `.progress.json` without `"mode"` is treated as multi (back-compat).

**document-systems `## Single mode overrides` must cover:** step selection (`doc`, `review` only; `discovery` / `root` / `subsystems` / `--no-discovery` / `--only` abort in single); Phase 1.5 type inference; Phase 1.6 progress shape (`system` + `status`); Phase 2 & 3 skipped (no Discovery, no root overview, no subsystem subdirs); Phase 4 single dispatch (one subagent, `<SINGLE_MODE> = true`, writes `<DOC_ROOT>/architecture.md`); Phase 5 single review handling; Phase 6 single wrap message; the single `.progress.json` shape; and the single-mode error rows.

**wiki-refine `## Single mode overrides` must cover:** Phase 1.3 single context (no `子系统清单`, one target); Phase 1.4 ready-line swap; Phase 2.2 single target (skip candidate matching / `--subsystem`); Phase 2.3 single dispatch (subagent edits the single doc directly — the "subagent must not edit the root doc" constraint is inverted); Phase 2.5 skipped (empty `root_suggestions`); Phase 3.2 wrap-line swaps.

**Reference prompts (unchanged by the reorg).** `subsystem-prompt.md`, `review-prompt.md`, and `refine-subagent-prompt.md` accept `<SINGLE_MODE>` and honor single mode via their own `## Single-system mode` block (edit the single doc directly, return empty `root_suggestions`, omit the parent-overview header).

---

## 10. Engine ↔ contract alignment (bidirectional completeness audit)

The prose contract (`wiki-principles.md`, `code-wiki-conventions.md`, `common-conventions.md`, `scenario-playbook.md`, templates) is the single source of truth; the engine's lint (`scripts/wiki_engine/lint/`) is the executor. The two must be bound bidirectionally and auditable, or they drift (this is the plan's largest risk: prose and code maintained separately).

**Direction A — every lint rule cites a contract clause.** Each engine rule carries its source clause in its registry entry, surfaced by `rule-catalog`. Examples: `Q10_FORMAT` → `wiki-principles §5`; `ANCHOR_NO_LINENO` → `wiki-principles §2`. Intercept: someone adds "tables must not exceed 20 rows" with no contract behind it → fail → either write it into the contract or delete the rule. **The engine may not invent constraints the contract does not state.**

**Direction B — every mechanically checkable contract clause either has an engine check or is explicitly marked `LLM-only`.** What a machine can verify must have a corresponding lint; clauses that genuinely need semantic judgement are marked `LLM-only`, documenting that the absence of an engine rule is deliberate, not an oversight. Example (has a rule): code-wiki-conventions §8 「数据名源码可 grep」 → `DATA_NAME_GREP`. Example (marked `LLM-only`): wiki-principles §3 ownership "is this a cross-system contract or an implementation-detail leak?" is undecidable mechanically — the engine only flags the signal (another subsystem's identifier appears), and the verdict is left to the review LLM, so that clause is marked `LLM-only`/hybrid. Intercept: the contract adds "§5 upstreams in alphabetical order" (mechanical) but no engine rule exists and it is not marked `LLM-only` → fail. **A mechanical clause may not be written without an enforcer.**

Operational meaning: **every contract change must be walked back through the engine once**, or the two eventually disagree.

## 11. Section-name constants ↔ templates/contract

Engine section-name constants (`scripts/wiki_engine/` literals used by `doc_kind`, `parser`, `address`, and `update_root` named regions) MUST equal the literal chapter names in the templates and contract. The Check 4 section-name alignment set is **extended** to include:

- the four common templates' three-section skeleton (`## 1. 范围与级别`, the type body heading, `## 待确认 / 疑问`);
- `references/common-conventions.md` (the four `common_type` values, the level names — now the full `level` enum **`repo` / `domain` / `global`** (engine `COMMON_LEVELS`), the frontmatter keys) — see also common-conventions §7;
- the new root chapter `## 仓内公共文档` (root template ↔ engine `update_root` `common_index_entry` region);
- the engine's table column orders for `subsystem_row` / `protocol_row` / `common_index_entry` ↔ the corresponding template table headers;
- the **domain landing index** `index.md` at `<WIKI_BASE>/<DOMAIN>/index.md` — engine-maintained, not skill-written directly;
- the engine `_root_common_index_entry` level→link-prefix map:
  - `repo` → `./_common/` (link within the same repo doc-root)
  - `domain` → `../_common/` (link up to the domain's `_common/`)
  - `global` → `../../_common/` (link up to the wiki root `_common/`)
  — this map lives in the engine (design §4.3) and must match any template that generates `common_index_entry` rows.

Renaming any of these requires updating the engine constant and the template/contract literal together.

## 12. Engine output language

Engine JSON carries English `rule_id` / `code` plus a `message_zh` field. Skills display ONLY `message_zh` to the user (per Check 5: user-facing prose is Chinese, agent-facing/code identifiers English). Mechanical check: every engine finding/error object has both an English code and a `message_zh`.

## 13. wiki-refine resolves the install root by probe order (no hardcoded user path)

`../wiki-refine/SKILL.md` and `../wiki-refine/references/refine-subagent-prompt.md` resolve the install root in this order, taking the first that exists:

1. **in-repo** — if the current repo can be located (`git rev-parse --show-toplevel` succeeds and `<repo-root>\document-systems\` exists), install root = `<repo-root>\document-systems` (friendly to codex / trae-cn, where the repo is the working dir);
2. **Claude Code junction** — else `~/.claude/skills/document-systems` (expand `%USERPROFILE%`, never literal `admin`);
3. **config override** — else an optional configured install root;
4. none of the three → abort with a Chinese contract-missing message.

The engine CLI and every contract file path are expansions of this resolved root. **Mechanical check: neither `SKILL.md` nor `refine-subagent-prompt.md` contains a `C:\Users\<user>\...` literal as the install root.** This refines Check 3's "absolute path" into "the absolute path that resolution produces", so codex / trae-cn and machine-swap / CI / container scenarios all work.

## 14. Engine tests green before dependent skill changes ship

A change to a skill that depends on the engine (wiki-refine flow, document-systems Phase E wiring) may not be declared done until `python -X utf8 -m unittest discover scripts/wiki_engine/tests` passes fully. The byte-exact `render(parse(x)) == x` round-trip must hold on every fixture (the B-gate first door).

## 15. MIGRATION.md stays in sync with engine operator names / contract regions

`MIGRATION.md` references engine operator names (`promote_to_common`, `move_with_reference`, `resolve_question`, `update_section`, `add_question`, `update_root`, `update_domain_index`) and the engine subcommand `resolve-domain`. Renaming an operator, a subcommand, or a named region requires updating `MIGRATION.md` in the same change. `MIGRATION.md` M0 documents the use of `resolve-domain --set` and `update_domain_index` (`--domain-index` flag) for domain migration.

## 16. Domain registry + mandatory domains

- The `<WIKI_BASE>/.wiki.json` domain registry MUST exist for any domained wiki; its absence is an error, not a fallback to flat mode. Both skills validate its presence (or create it via `--init-domains`) before resolving paths.
- `resolve-domain` MUST never produce a flat (domain-less) path. There is no flat branch in either skill — flat output paths are a defect.
- No skill run may emit `<DOC_ROOT>` = `<WIKI_BASE>/<REPO_NAME>` (two segments only). The three-segment form `<WIKI_BASE>/<DOMAIN>/<REPO_NAME>` is the only valid shape.
- **KNOWN-TODO (Plan-4 final-review recommendation, not yet implemented):** The engine should raise `UsageError` when `level` is supplied with a value outside the `COMMON_LEVELS` enum (`repo`, `domain`, `global`). Until this is implemented, out-of-enum level values silently pass the engine. When implemented, add an engine-test assertion and update this check to reflect enforcement.
