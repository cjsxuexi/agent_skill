# Common-Document Conventions

Conventions for **shared documents** owned by the wiki engine — facts that more than one
subsystem (or more than one repository) needs, with no single subsystem as their natural
owner. Apply when promoting, authoring, or linting a document under a `_common/` namespace.

This file is the single source of truth for: the directory namespace model, the three-level
`_common` semantics, the placement decision ladder, the four common-document types and their
light structure, the read-source boundary ladder, and the engine's ignore-glob list. It is
readable on its own; where a rule extends a general wiki rule, the clause is named (e.g.
"wiki-principles §5") so the engine can cite it.

---

## 1. Directory namespace model (engine's first pass: classify top-level directories)

Before any document is classified by kind, the engine classifies the **top-level directories**
under `WIKI_BASE`. A leading `_` marks a **non-business namespace** so it can never collide with
a real repository or subsystem name.

| Class | Test | Examples | How the engine treats it |
|---|---|---|---|
| Domain directory | top-level dir NOT starting with `_` or `.` AND its name appears in `.wiki.json`'s `domains` list | `autonomous-driving/`, `fleet-mgmt/` | a container for business wiki repos; the engine resolves repos under it via `resolve-domain`; not linted directly |
| Business wiki repo | non-`_`/`.` dir INSIDE a domain directory | `fabusurfer`, `fms-server`, `charge-manage-platform` (under their domain dir) | governed by the strict contract (then refined by DocKind) |
| Engine-managed common namespace | exactly `_common` (global `<WIKI_BASE>/_common/`, domain-level `<WIKI_BASE>/<DOMAIN>/_common/`, repo-level `<DOC_ROOT>/_common/`) | `_common/` | light contract; `promote_to_common` / `init-common` / `questions` / light-lint operate here; referenced by business docs via `../_common/`, `../../_common/`, `../../../_common/` |
| Engine-ignored reserved area | any other `_`-prefixed dir | `_meta/` (gitnexus notes, tool/process docs) | never linted, never touched, no contract required — a free area |

Directories starting with `.` (`.git`, `.idea`, `.claude`) are always skipped. The same rule
applies inside a repo: under `<DOC_ROOT>`, `_common` is the repo-level common, any other `_*` is
ignored, and everything else is a subsystem directory. The distinction between `_common` and
`_meta` is "engine-managed (needs a contract, gets referenced)" vs "engine-ignored (free notes)".

---

## 2. Three-level common

There are three `_common/` namespaces. `<WIKI_BASE>` is a single git work tree, so all levels live
inside it and relative links reach across them:

- **Global** `<WIKI_BASE>/_common/` — facts shared **across domains** (or company-wide standards).
- **Domain-level** `<WIKI_BASE>/<DOMAIN>/_common/` — facts shared by **two or more repositories inside one domain**, with no single repo as owner.
- **Repo-level** `<DOC_ROOT>/_common/` — facts shared by **two or more subsystems inside one repository**, with no single subsystem as owner.

Reference path rule (computed from the source document's depth; `<DOC_ROOT>` = `<WIKI_BASE>/<DOMAIN>/<REPO_NAME>`):

| 源文档 (source doc) | → 仓 `_common` | → 域 `_common` | → 全局 `_common` |
|---|---|---|---|
| `<DOC_ROOT>/<subsystem>/architecture.md` | `../_common/<name>.md` | `../../_common/<name>.md` | `../../../_common/<name>.md` |
| `<DOC_ROOT>/architecture.md` (root / single) | `./_common/<name>.md` | `../_common/<name>.md` | `../../_common/<name>.md` |

Cross-document links into a common document MUST carry a section anchor (wiki-principles §4),
computed with the engine's GitHub-exact slugger.

---

## 3. Placement decision ladder (where does a fact live?)

When a fact surfaces, walk the ladder top-down and stop at the first match. **Prefer the lowest
level** that fits.

1. **Owned by a single subsystem** → leave it in that subsystem's document; everyone else links
   to it (wiki-principles §3 ownership). Promotion is NOT warranted.
2. **Shared by ≥2 subsystems in this repo, no single owner** → repo-level common
   (`<DOC_ROOT>/_common/`).
3. **Shared by ≥2 repositories in this domain, no single repo as owner** → domain-level common
   (`<WIKI_BASE>/<DOMAIN>/_common/`). Requires explicit confirmation at the 2.5.b 公共化门禁.
4. **Shared across ≥2 domains, or a company-wide standard** → global common
   (`<WIKI_BASE>/_common/`). Requires explicit confirmation at the 2.5.b 公共化门禁.

When in doubt, choose the lower level and record a "建议域级公共化"/"建议全局化" entry in the
common document's `## 待确认 / 疑问` (or the subsystem's §10) rather than promoting speculatively.

**Default level.** Unless rung ③ or ④ is positively established, the `level` of a promotion is
always `repo` — this is the engine's default value. Choosing `domain` or `global` requires the
level to be stated explicitly at the 2.5.b 公共化门禁 and confirmed by the user. (Until real
cross-repo or cross-domain consumers appear, the domain and global `_common/` namespaces stay
legitimately near-empty — only their `index.md`.)

---

## 4. The four common-document types

A common document is exactly one of four types (no "other"):

| `common_type` | Holds | Type body |
|---|---|---|
| `glossary` | a cluster of terms / vocabulary | a term table |
| `shared-lib` | the contract of a shared library | external contract / call surface + consumers; NO library-internal details |
| `protocol` | a public protocol | protocol definition + producers / consumers |
| `infra` | an infrastructure convention | the convention + where it applies |

---

## 5. Light structure (thin skeleton)

Every common document keeps a **thin three-section skeleton**; prose inside each section is free:

```
## 1. 范围与级别       (scope + which level this doc lives at, and which subsystems consume it)
## <type body>         (the type's main section — glossary table / shared-lib contract / etc.)
## 待确认 / 疑问        (open questions, same entry format as wiki-principles §5)
```

This skeleton is the price of being queryable. A uniform `## 待确认 / 疑问` lets the engine's
`questions` command enumerate common open items alongside every subsystem §10; predictable
section titles keep `../../_common/x.md#<anchor>` references stable. **Fully unstructured common
documents are not allowed** — they break `questions`/anchors and regress to the ad-hoc state.

Common documents do **not** carry the subsystem §1–§10 contract: no fixed ten sections, no §11+
prohibition. They follow light rules only — frontmatter + the `## 待确认 / 疑问` tail + anchor
format + no speculation words + identifiers verbatim.

**Document granularity.** One document = one coherent topic cluster (e.g.
`coordinate-heading-terms.md` collects one group of coordinate / heading terms). The index lists
to the **document** level; a specific entry inside is found by anchor or grep. This is neither
"one term per file" (too fragmented) nor "one type, one giant file" (too bloated).

---

## 6. Organization model: four types as axis + index navigation + two query layers

The `_common/` namespace is organized **by the four types, with a thin skeleton inside each type,
plus an `index.md` for navigation**.

- **Discovery / navigation** ("what shared documents exist") is served by `_common/index.md`,
  grouped by the four types, and kept **minimal** — each row is only `file / level / one sentence
  / owns`, and **must not restate content** (otherwise the index becomes a drifting derived file,
  forbidden by wiki-principles §7).
- **Cross-document query** ("list every open question", "who references this document / term") is
  computed live by the engine (`questions` / `refs` / grep) and **never written into the index**
  (wiki-principles §7 native-tools-first).

`index.md` is the one derived file the engine is allowed to maintain at both the global and
domain levels (each is a thin navigation index for its `_common/` namespace, maintained by the
engine's `update-domain-index` op). Repo-level `_common/` needs no index — the repo root
document's `## 仓内公共文档` section already lists its members.

---

## 7. Frontmatter

Every common document begins with YAML frontmatter:

```yaml
---
common_type: glossary | shared-lib | protocol | infra
level: repo | domain | global
owns: <stable id of the fact this document owns>
---
```

`owns` is a stable, human-assigned identifier for the shared fact (e.g. `coordinate-heading-terms`,
`ego-info-source`). File names are kebab-case English (`ego-info-source.md`).

---

## 8. Ownership of shared facts

A common document **owns** the shared facts it holds. Subsystem documents that use those facts
MUST anchor-reference the common document (wiki-principles §3 / §4) and MUST NOT copy the internal
detail. This is the same ownership rule as between two subsystems, with the common document as the
designated owner.

For `shared-lib` common documents, attribution of facts learned by reading a jar/SDK under user
authorization follows code-wiki-conventions §3 (`> 来源：经用户授权阅读 <对象>（YYYY-MM-DD）`).

---

## 9. Read-source boundary ladder + escalation (decision 5)

Light documents (common + ancillary) MAY read **across subsystems** within the current repo to
trace a shared fact to its call site, but **stop at jar / SDK boundaries** (code-wiki-conventions
§1 / §2). Strict documents (a subsystem's own `architecture.md`) still read **only their own
subsystem's source**.

**Escalation** — when tracing genuinely requires reading a forbidden zone (another subsystem's
source for a strict task, a jar/SDK, or another repository):

1. Complete every part that does NOT depend on the forbidden zone first.
2. Return an `escalation_request` with `zones:[{kind, target, reason}]`, where
   `kind ∈ other_subsystem | jar_sdk | other_repo` and `target` is the concrete subsystem name /
   jar name / repo name.
3. The main agent asks the user. On approval the topic is re-dispatched with `<EXPANDED_SCOPE>`;
   on refusal the gap is logged as a §10 entry.

Escalation only widens **reading**; it never changes the ownership ("writing") rules. Content
obtained by reading a jar/SDK under user authorization is annotated
`> 来源：经用户授权阅读 <对象>（YYYY-MM-DD）` and preferentially lands in a `shared-lib` common
document.

---

## 10. Ignore globs (engine reads this block)

Paths matching any glob below are `IGNORED` DocKind: never parsed for contract compliance, never
linted, never targeted by operations. The engine parses the fenced block line by line: a line whose
first non-whitespace character is `#` is a comment and is skipped, blank lines are skipped, and
every other line (trimmed) is one glob pattern. Keep it machine-parseable.

```ignore-globs
issue/**
whole_architecture.md
生产问题速查.md
spec/**
**/.review.md
```

(Top-level non-`_common` `_*` directories are already excluded by the §1 directory-namespace pass
and need no glob here.)
