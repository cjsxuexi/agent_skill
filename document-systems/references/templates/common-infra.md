<!--
Template for an `infra` common document (infrastructure convention).

Usage: the engine reads this file, REMOVES this leading comment block (match a
standalone `^-->` terminator), substitutes the placeholders below, and writes the
result under `_common/<OWNS>.md`. The engine does NOT embed a copy of this template;
this file is the single source.

Placeholders:
  <LEVEL>       repo | global (from the promote op; default repo)
  <TITLE>       the document title (from title_file)
  <SCOPE_BODY>  one sentence: which subsystems / repos this convention applies to, at which level
                (engine generates from the op's source list + level)
  <TYPE_BODY>   the convention + its applicable scope (from body_file)
  <QUESTIONS>   open-question entries (wiki-principles §5 format) or 无 (default)

Structure invariant: exactly three sections — `## 1. 范围与级别`, the type body
`## 2. 约定与适用范围`, and `## 待确认 / 疑问`. Prose inside each section is free.
-->
---
common_type: infra
level: <LEVEL>
owns: <OWNS>
---

# <TITLE>

## 1. 范围与级别

<SCOPE_BODY>

## 2. 约定与适用范围

<TYPE_BODY>

## 待确认 / 疑问

<QUESTIONS>
