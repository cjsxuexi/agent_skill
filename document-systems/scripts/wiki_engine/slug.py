"""GitHub-exact heading slugger — the single source of truth for every anchor the
engine validates or generates (plan §3 约束 1).

GitHub (via its html-pipeline TableOfContentsFilter) produces a heading anchor by:
    1. lower-casing the heading's text,
    2. removing every character that is not a Unicode "word" character, a space,
       or a hyphen  (Ruby ``/[^\\p{Word}\\- ]/u``; \\p{Word} = letters L + marks M
       + decimal digits Nd + connector punctuation Pc, which includes ``_``),
    3. replacing each remaining space with a single hyphen (runs are NOT collapsed,
       leading/trailing hyphens are NOT trimmed).

Duplicate headings in one document get a ``-1`` / ``-2`` … suffix, matching
github-slugger's occurrence counter.

Golden wild case (real, from D:\\wiki\\fabusurfer\\port-vehicle/architecture.md):
    "6.6 OTA / 版本 / 文件日志流"  ->  "66-ota--版本--文件日志流"
(`.` and the two `/` are dropped; the spaces that flanked each `/` survive and each
become a hyphen, producing the double hyphens.)
"""

import unicodedata


def _is_word_char(ch):
    """Replicate Ruby ``\\p{Word}``: letters (L*), marks (M*), decimal digits (Nd),
    connector punctuation (Pc, e.g. underscore)."""
    cat = unicodedata.category(ch)
    return cat[0] in ("L", "M") or cat == "Nd" or cat == "Pc"


def slug(text):
    """Pure GitHub slug for a single heading text (no de-duplication)."""
    lowered = text.lower()
    kept = []
    for ch in lowered:
        if ch == " " or ch == "-":
            kept.append(ch)
        elif _is_word_char(ch):
            kept.append(ch)
        # everything else is dropped
    return "".join(kept).replace(" ", "-")


class Slugger:
    """Stateful slugger that de-duplicates within one document, exactly as
    github-slugger does (first ``foo``, then ``foo-1``, ``foo-2`` …)."""

    def __init__(self):
        self.occurrences = {}

    def slug(self, text):
        base = slug(text)
        result = base
        while result in self.occurrences:
            self.occurrences[base] += 1
            result = "{}-{}".format(base, self.occurrences[base])
        self.occurrences[result] = 0
        return result

    def reset(self):
        self.occurrences.clear()
