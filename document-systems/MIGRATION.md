# Wiki Migration Plan (M1–M5)

Existing `D:\wiki` content predates the wiki-engine contracts and carries the drift this refactor
exists to fix. This file is the **plan** for cleaning it up — **documentation only**. Executing it is
the out-of-scope Phase F: each step runs in a future session, one at a time, with user confirmation,
preferably through the engine so every change is contract-validated and atomic.

Each step is tagged `[engine]` (a `wiki_engine` transaction), `[refine]` (driven inside a `/wiki-refine`
session), or `[manual]` (a human decision / one-off edit). Operator names referenced here track the
engine (MAINTAINER §15): `promote_to_common` / `move_with_reference` / `resolve_question` /
`update_section` / `add_question` / `update_root` / `update_domain_index`; subcommand: `resolve-domain`.

---

## M0 — 域化迁移 (domain migration)  `[engine]` `[manual]`

Run **before M1–M5**. M1–M5 remain verbatim and fall inside the same governance window (one
`git -C <WIKI_BASE> diff` review + commit per completed step).

1. **建域注册表** — run `/document-systems --init-domains`. This writes `<WIKI_BASE>/.wiki.json`
   with the domain whitelist (e.g. `["old_project","fms"]`) and initialises an empty `repos` map.
   `[engine]`

2. **迁移现有 flat 仓目录** — for each existing flat repo directory at `<WIKI_BASE>/<repo>`, run:
   ```
   git -C <WIKI_BASE> mv <repo> <domain>/<repo>
   ```
   Intra-repo links are relative (`./<sub>/architecture.md`, `../_common/…`), so they survive the
   move intact — verified: the wiki contains 0 `](../../)` cross-repo absolute links. `[manual]`

3. **刷新根样板** — for repos whose root doc (`<domain>/<repo>/architecture.md`) was generated with
   the two-level `## 仓内公共文档` boilerplate (`./_common/` and `../../_common/` only), run:
   ```
   /document-systems --step=root
   ```
   to regenerate it with the three-level wording (`./_common/`, `../_common/`, `../../_common/`). `[engine]`

4. **固化 repo→domain 映射** — for each migrated repo, run:
   ```
   resolve-domain --repo <REPO_ROOT> --wiki <WIKI_BASE> --set <domain>
   ```
   This persists the `repo→domain` mapping into `.wiki.json`'s `repos` object. `[engine]`

5. **生成域索引** — for each domain, run:
   ```
   /document-systems --domain-index=<domain>
   ```
   This builds `<WIKI_BASE>/<domain>/index.md` (the domain landing index, engine-maintained). `[engine]`

- **Gate**: `/wiki-refine --lint` over the whole wiki is clean; `git -C <WIKI_BASE> diff` reviewed
  before committing the wiki repo.

---

## M1 — Dissolve `fabusurfer/global/` into the repo-level `_common/`  `[refine]` `[engine]`

`fabusurfer/global/coordinate-heading-terms.md` is a self-made common embryo (problem B in the plan).
Move it to the engine-managed namespace as a `glossary` common document at the repo level.

- **Target**: `fabusurfer/_common/coordinate-heading-terms.md`, `common_type: glossary`, `level: repo`,
  `owns: coordinate-heading-terms`.
- **How**: in a `/wiki-refine` session, classify the topic as S4 and run `promote_to_common(level=repo,
  type=glossary)` (or, since the content already exists, `init-common` to scaffold + a `move_with_reference`
  to relocate the body). The engine writes the frontmatter + thin skeleton and rewrites every referrer to
  `../_common/coordinate-heading-terms.md#<anchor>`.
- **Then**: remove the empty `fabusurfer/global/` directory `[manual]`, and add a `common_index_entry`
  to the root doc's `## 仓内公共文档` via `update_root` `[engine]`.
- **Gate**: `refs --path fabusurfer/_common/coordinate-heading-terms.md --scope doc-root` finds the
  expected referrers; `lint` on the new common doc is clean.

## M2 — Fix `port-data/architecture.md` §11  `[refine]` `[engine]` `[manual]`

`port-data` grew an illegal `## 11. 用户操作维度报表数据链路核对` (strict §11+ forbidden) plus a derived
`lineage-open-questions.md` (problem A / wiki-principles §7).

- **Five architecture-adjustment points** in the §11 body → fold the verified facts into §6 / §7 body via
  `update_section` `[engine]` (e.g. the corrected `ctos` ingestion chain, the report data-asset rows).
- **`PD-LIN-001..009`** (the open-question list) → §10 entries via `add_question`, one per item, each in
  the `[§位置] …。已检查：…。建议核实方向：…` format `[engine]`. Carry the explicit `PD-LIN-00x` id inside
  the first sentence so the question keeps a cross-session identity (plan §6.3).
- **Remove the `## 11.` section** once its content has landed in §6/§7/§10 (the engine will then stop
  reporting `STRUCT_NO_SECTION_11PLUS` for that doc) `[engine]`/`[manual]`.
- **Dissolve `lineage-open-questions.md`** (its questions are now §10 entries) `[manual]`; **keep**
  `business-report-lineage-analysis.md` as an ANCILLARY doc and give it the light frontmatter (M4) `[manual]`.
- **Gate**: `lint --path fabusurfer/port-data --recursive --source-root <repo>` shows no
  `STRUCT_NO_SECTION_11PLUS` and no `LINK_DERIVED_FILE`; the relocated facts pass the §6↔§7 and
  data-name checks.

## M3 — Confirm the ignore-glob allowlist  `[engine]`

`issue/**`, `whole_architecture.md`, `spec/**`, and `**/.review.md` are IGNORED DocKind (read from
`common-conventions.md`'s `ignore-globs` block). Confirm the existing `fabusurfer/issue/…`,
`fabusurfer/whole_architecture.md`, and `fabusurfer/spec/…` files are no longer linted or misreported.

- **How**: `lint --path fabusurfer --recursive` and verify none of those paths appear in the findings.
- **Note**: `issue/**` stays IGNORED for now; its content migrates into `spec/**` (owned by
  `spec-driven-implementation`) later — out of scope here (plan §13 决策 #3).
- **Gate**: no findings reference an ignored path.

## M4 — Backfill light frontmatter on existing ancillary docs  `[manual]` `[refine]`

Ancillary docs (`port-data/business-*.md`, `port-device/alarm-architecture.md`,
`port-telecontrol/runbook-*.md`, etc.) predate the light contract. Add the light frontmatter
(`> 由 /wiki-refine 在 <YYYY-MM-DD> 补充话题：…` or a doc-appropriate header) and, where they carry open
questions, a unified `## 待确认 / 疑问` tail so `questions` can enumerate them.

- **How**: opportunistically during `/wiki-refine` sessions, or as a one-off pass.
- **Gate**: `questions --path fabusurfer --recursive` enumerates ancillary open items alongside subsystem §10.
- **Known real drift** the lint already surfaces and M4 addresses: `ANCHOR_NO_LINENO` line-number anchors
  in `port-data/data-feedback-system.md` and `port-telecontrol/runbook-vehicle-location-ws.md` (convert
  `Foo.java:53` → `Class#method (path)`).

## M5 — First global `_common/` documents  `[manual]`

There is currently no confirmed cross-repo shared fact (plan §13 决策 #1: 先一律仓库级). So the global
`D:\wiki\_common\` layer stays legitimately near-empty — only the engine-maintained `index.md`
(`init-common --level global` seeds it). When a fact is genuinely consumed by a second repository (e.g.
`fabusurfer` and `fms-server` sharing a protocol), promote it with `promote_to_common(level=global)` and
the 2.5.b gate's explicit `global` confirmation.

- **Gate**: any global common doc has `level: global` and at least two consuming repos documented; until
  then, M5 produces no global documents.

---

## Execution notes

- Run M-steps individually with user confirmation; prefer `apply --dry-run` first on every transaction.
- M1 and M2 are the highest-value (they remove the two concrete contract violations the plan opens with).
- After each step, review with `git -C <DOC_GIT_ROOT> diff` before committing the wiki repo.
