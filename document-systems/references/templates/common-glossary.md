<!--
Template for a `glossary` common document (term cluster).

Usage: the engine reads this file, REMOVES this leading comment block (match a
standalone `^-->` terminator), substitutes the placeholders below, and writes the
result under `_common/<OWNS>.md`. The engine does NOT embed a copy of this template;
this file is the single source.

Placeholders:
  <LEVEL>       repo | global (from the promote op; default repo)
  <TITLE>       the document title (from title_file)
  <SCOPE_BODY>  one sentence: which subsystems / repos consume these terms
                (engine generates from the op's source list + level)
  <TYPE_BODY>   the glossary table rows (from body_file), one term per row
  <QUESTIONS>   open-question entries (wiki-principles §5 format) or 无 (default)

Structure invariant: exactly three sections — `## 1. 范围与级别`, the type body
`## 2. 术语表`, and `## 待确认 / 疑问`. Prose inside each section is free.
-->
---
common_type: glossary
level: <LEVEL>
owns: <OWNS>
---

# <TITLE>

## 1. 范围与级别

<SCOPE_BODY>

## 2. 术语表

| 术语 | 含义 | 来源 / 出处 |
|---|---|---|
<TYPE_BODY>

## 待确认 / 疑问

<QUESTIONS>
