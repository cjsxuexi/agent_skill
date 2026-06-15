# Scenario Playbook (S1–S8)

When refining a wiki through conversation, every topic maps to one or more of eight modification
scenarios. Each scenario fixes the engine transaction shape and the user gate. The engine
**hard-rejects** illegal operations; this playbook tells the agent which transaction to build and
which classification questions to answer. Read this in Round 2 (Classify).

The agent decides **semantics** (which scenario, who owns a fact, what level, full vs partial
resolution, the Chinese prose). The engine validates only the **structured result**.

---

## The eight scenarios

| ID | Trigger | Agent's classification call | Engine transaction shape | User gate |
|---|---|---|---|---|
| **S1** §10 fully resolved | an existing §10 entry is completely answered by tracing / user input, no residue | "Is **every** clause of the entry closed? Any residue → S2" | `resolve_question(full)` coupled in the **same transaction** with `update_section` (write the conclusion into the body). Engine **forces the coupling**: deleting a §10 entry without a body landing is hard-rejected (or supply an existing-anchor proof that the conclusion is already in the body) | existing A/R/E |
| **S2** §10 partially resolved | some clauses closed, some still unknown | "Which clauses close, which stay? How to re-state the residue?" | `resolve_question(partial, <rewritten residue text>)` + `update_section` for the confirmed part | A/R/E |
| **S3** same fact detailed in multiple docs | tracing finds the same internal fact written in detail in ≥2 documents | "Who is the owner?" Guide: the subsystem that contains the defining `Class#method` owns it | `move_with_reference`: the owner keeps the detail; every other site is replaced with an anchor reference + one-sentence summary | A/R/E |
| **S4** cross-system shared fact | ≥2 subsystems need it, no single owner (term / shared lib / protocol / infra) | placement ladder (common-conventions §3) sets level + type | `promote_to_common(level, type)` + `move_with_reference` at each site + scaffold the target common document if absent; **fully atomic** | **新增公共化门禁 A/S/R** (S = not yet promoted, record "建议公共化" in the relevant subsystems' §10) |
| **S5** newly verified fact | tracing finds an unrecorded, code-verifiable fact | "Which section? Is the data name greppable?" | `update_section` (engine lint guards the six channels and §6↔§7 consistency) | A/R/E |
| **S6** new uncertainty | a chain doesn't close / producer unknown / boundary fuzzy | phrase as `[§<位置>] …。已检查：…。建议核实方向：…` | `add_question` (engine validates the §10 format) | A/R/E |
| **S7** user-dictated knowledge | `<USER_SUPPLEMENT>` carries jar/SDK internals, runtime config, business rules | "Which section? Keep separate from code-verifiable content" | `update_section` with `> 来源：用户口述（日期）` (data names are grep-exempt but must carry the annotation) | A/R/E |
| **S8** root-document impact | subsystem row missing / dependency edge wrong / protocol row missing / aux-resource drift / common-index row missing | "Which root artifact? Build the exact row / edge" | the subagent returns a ready `update_root` payload; the main agent applies it **with the engine** after user confirmation (replacing the old manual Edit) | existing root gate A/S/R, now engine-applied |

---

## Three classification guides

### Guide 1 — Ownership (S3)

The owner of an internal fact is the subsystem whose source **defines** it (the `Class#method`
that produces / writes / originates the fact). The other subsystems merely consume it and must
reference, not copy. If the defining site is a jar/SDK or another repo, the fact is a candidate
for a `shared-lib` common document (S4), not a subsystem detail.

### Guide 2 — Common level ladder (S4)

Walk common-conventions §3 top-down, stop at the first match, prefer the lowest level:

1. single subsystem owns it → not common (use S3);
2. ≥2 subsystems in this repo share it, no owner → `level=repo`;
3. a second repo consumes it / company standard → `level=global`.

Default is `repo`. `global` requires explicit confirmation at the 2.5.b gate (common-conventions
§3 default-level rule).

### Guide 3 — Full vs partial resolution (S1 vs S2)

Read each clause of the §10 entry. If **every** clause is closed by evidence, it is S1 (full);
if any clause still has no code/anchor/user evidence, it is S2 (partial) — close what you can,
rewrite the residue as a tighter §10 entry. When unsure, prefer S2: a too-eager full-resolve that
deletes a still-open question is worse than leaving a narrowed residue.

---

## Cross-cutting rules

- **One topic may hit multiple scenarios** → compose them into **one transaction**, `--dry-run`
  to a clean state first, then apply for real (atomic: all-or-nothing).
- **Owner / level / full-vs-partial are the agent's semantic calls**; the engine only validates
  the structured result (addressing resolves, bytes match, no new blocking lint).
- **Build a single transaction per topic.** Root-document impact (S8) is the exception: it is
  returned as a separate `update_root` payload, not folded into the section transaction.

---

## Escalation flow

When Round-1 tracing hits a forbidden zone (another subsystem's source for a strict task, a
jar/SDK, or another repo) **and the read is genuinely necessary**:

1. Finish every part that does not depend on the forbidden zone.
2. Return `status: "blocked_on_escalation"` with
   `escalation_request: { zones: [ { kind, target, reason } ] }`, where
   `kind ∈ other_subsystem | jar_sdk | other_repo` and `target` is the concrete name.
3. The main agent prints the zone / reason / expected benefit and asks the user (gate 2.4.b).
   - **A** → re-dispatch the same topic with `<EXPANDED_SCOPE>` carrying the approved zones.
   - **R** → keep the completed part; log the gap as a §10 entry.

Escalation widens **reading only**; ownership ("writing") rules are unchanged (common-conventions
§9). Content read from a jar/SDK under authorization is annotated
`> 来源：经用户授权阅读 <对象>（YYYY-MM-DD）` and preferentially lands in a `shared-lib` common
document.
