<!--
Template for a `shared-lib` common document (shared-library contract).

Usage: the engine reads this file, REMOVES this leading comment block (match a
standalone `^-->` terminator), substitutes the placeholders below, and writes the
result under `_common/<OWNS>.md`. The engine does NOT embed a copy of this template;
this file is the single source.

Placeholders:
  <LEVEL>       repo | global (from the promote op; default repo)
  <TITLE>       the document title (from title_file)
  <SCOPE_BODY>  one sentence: which subsystems / repos consume this library, at which level
                (engine generates from the op's source list + level)
  <TYPE_BODY>   the external contract / call surface + consumers (from body_file).
                Document ONLY the call surface and wire contract; NEVER library internals
                (code-wiki-conventions §2). Facts read from a jar/SDK under user authorization
                carry `> 来源：经用户授权阅读 <对象>（YYYY-MM-DD）` (code-wiki-conventions §3).
  <QUESTIONS>   open-question entries (wiki-principles §5 format) or 无 (default)

Structure invariant: exactly three sections — `## 1. 范围与级别`, the type body
`## 2. 对外契约与使用方`, and `## 待确认 / 疑问`. Prose inside each section is free.
-->
---
common_type: shared-lib
level: <LEVEL>
owns: <OWNS>
---

# <TITLE>

## 1. 范围与级别

<SCOPE_BODY>

## 2. 对外契约与使用方

<TYPE_BODY>

## 待确认 / 疑问

<QUESTIONS>
