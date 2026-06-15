# Wiki Principles

General principles for wiki-style knowledge documentation. Apply to any wiki produced by this family of skills.

---

## 1. Fixed section contract

**Rule**: each wiki document follows a predeclared section sequence (`§1`–`§N`). Titles, order, and numbering are fixed. Empty sections must contain the literal text `无` (Chinese: "none"). Do not delete, rename, or reorder sections.

**Why**: section numbers and titles are the anchor targets for cross-doc links (`#N-章节名`). Renaming or reordering instantly breaks every existing link and breaks section-based LLM lookups (e.g. "find §6 业务流").

**Example**:

```
## 6. 业务流
（actual content）

## 7. 数据资产
无
```

**Counter-example**: rename §6 to「业务逻辑」; move §10 before §5; delete an empty section to "save space".

---

## 2. Source anchor format: `Class#method (path)`, no line numbers

**Rule**: references to specific source elements use `Class#method (relative/path.ext)`. The path is relative to the documented object's root. Never include line numbers.

**Why**: line numbers drift with every commit. Class + method names + relative path are stable and greppable.

**Example**: `OrderService#refund (src/main/java/com/foo/OrderService.java)`

**Counter-examples**:

- `OrderService.java:L28-L45` — line numbers will drift
- `OrderService.refund` — no path, file can't be located

---

## 3. Ownership: a doc describes only its own object's internals

**Rule**: a wiki document describes the internals of *its own object* (subsystem, module, domain unit) only. References to external objects use a markdown link with a section anchor plus a brief natural-language summary. Never write external objects' internal identifiers (class names, method names, table names, topic names) in the current doc. A fact shared by several objects with no single natural owner is assigned to one **designated owner document**; every other document references it with a section anchor and does not copy its internal detail.

**Why**: external internals belong to the other doc's ownership. Writing them here causes duplication, drift, and review-time ownership violations.

**Example**:

```
调用 [port-auth § 对外接口](../port-auth/architecture.md#4-对外接口) 校验 token
```

**Counter-example**:

```
调用 AuthController.verify()   ← AuthController is not in the current object
```

---

## 4. Cross-doc link precision: always include section anchors

**Rule**: cross-doc references use `[X § 章节](../X/foo.md#N-章节)`, where the link includes the target document's section number and title as the anchor.

**Why**: file-level links are too coarse — readers still have to search inside the target doc. Section-anchored links let the reader jump to the exact section, and give automated tools a single point of validation.

**Example**: `[port-auth § 对外接口](../port-auth/architecture.md#4-对外接口)`

**Counter-example**: `[port-auth](../port-auth/architecture.md)` — no anchor

---

## 5. Immediate uncertainty logging in §10; no speculation in §1–§9

**Rule**: any point that cannot be verified during analysis (unclosed call chains, unidentified callers, unclear config effects, ambiguous cross-object boundaries) must be logged immediately into §10 待确认 / 疑问. Speculation words ("可能" / "似乎" / "估计" / "推测" / "应该是") must not appear in §1–§9.

**Format**:

```
- [§<位置>] <疑问描述>。已检查：<相对路径文件清单>。建议核实方向：<...>
```

**Why**: uncertain content mixed into the main body is read as fact by later readers. A centralized §10 supports cross-LLM collaboration and user review, and lets tools `grep "## 10. 待确认"` enumerate every open question across docs.

**Example**:

```
- [§6.3 数据交互] kafka topic `device.event.raw` 仅见消费方，未找到生产方。已检查：KafkaConfig.java、application.yml。建议核实方向：检查 port-gateway 是否生产该 topic。
```

**Counter-example**: writing 「可能由 port-gateway 推送该 topic」 in the §6 body — speculation leaked into the main content.

---

## 6. Inverted-index pattern: dedicated reverse-lookup section by attribute

**Rule**: for each class of asset (the specific form depends on the wiki domain), the document must include — in addition to the forward (entry-point-ordered) description — a dedicated section organized by the asset's attributes, listing "this asset is used by which entries".

**Why**: impact analysis often needs reverse lookup ("given this asset, which entries are affected?"). Forward-only organization cannot answer this without re-scanning the source.

**Applies to**: any one-to-many asset ↔ user relationship.

**Examples** (depending on wiki domain):

- Code wiki: by table name / topic / endpoint, list which entries read / write it
- Prompts library wiki: by tool / model / scenario, list which prompts use it
- Decision-record wiki: by affected system, list which decisions constrain it

**Counter-example**: only writing "this entry uses A, uses B" under each entry, with no "A is used by which entries" reverse section.

---

## 7. Native tools first: do not generate derived files that overlap with git / IDE / grep

**Rule**: do not generate `.changes.md` / `.questions.md` / `.history.md` / `.index.md` or similar files that "re-summarize already-known facts". Use native tools for change tracking, cross-doc search, and history.

**Why**: derived files start drifting the moment they're written, doubling maintenance cost; LLM re-summarization always introduces distortion.

**Replacement table**:

| Need | Don't generate | Use instead |
|---|---|---|
| Compare against last run | `.changes.md` | `git diff HEAD -- <path>` or IDE line-level diff |
| Cross-doc search for questions / assets | `.questions.md` / `.assets-index.md` | `grep -rn` or IDE global search |
| History review / rollback | `.history.md` / `.prev.md` | `git log` / `git restore --source=<rev>` |

**Example**: to see all §10 questions, run `grep -rnF "## 10. 待确认" <DOC_ROOT>/`. Do not auto-generate a `.questions.md` aggregation.

**Counter-example**: every run produces `<DOC_ROOT>/.changes.md` paraphrasing what git diff already records precisely — LLM re-summarization adds no value and introduces drift.

---

## 8. Multi-round self-review: executable checklist, not "read again"

**Rule**: before a subagent finalizes output, it must run an explicit self-review pass. Each checklist item must be a concrete, checkable action — not a vague "read the doc once more".

**Why**: first-pass LLM output frequently violates contracts (missing sections, smuggled speculation, missing anchors, ownership crossing). An executable checklist catches the systemic errors.

**Example**:

```
Round 3 self-review:
- [ ] Did §10 capture every uncertain point flagged during Round 2?
- [ ] Are all source-code references in `Class#method (path)` form with no line numbers?
- [ ] Do all cross-doc links include section anchors?
- [ ] Does §1–§9 body contain any speculation words ("可能 / 似乎 / 推测")?
```

**Counter-example**: "Round 3: read the doc once more to confirm" — not verifiable, will be skipped.

---

## 9. Preserve identifiers verbatim

**Rule**: identifiers and proper nouns from the original source — names, terms, technical labels — are preserved verbatim. No translation, no naming-convention normalization, no simplification.

**Why**: identifiers are grep / cross-doc lookup anchors. Any transformation breaks grep hits and introduces source-doc drift.

**Applies to** (depending on wiki domain):

- Code wiki: class names, method names, table names, topic names, Redis keys, config keys, env vars, error codes, Bean names, framework names
- Decision / process wiki: system names, role names, stage names, state-machine labels
- Any wiki: external product names, tool names, API names

**Example**: if the source is `OrderStatusEnum.PAYING`, write `OrderStatusEnum.PAYING`.

**Counter-examples**:

- Translate to「订单状态枚举.支付中」
- Normalize to `order_status_enum.paying` (snake-case)
- Simplify to `PAYING` (drop namespace)
