"""Lint infrastructure: Finding, Rule, LintContext (plan §6.6, MAINTAINER §10/§12).

Every Finding carries an English ``rule_id`` + a Chinese ``message_zh`` (skills show only
the latter). The delta key is ``(rule_id, doc, position, sha1(message_zh)[:8])`` — a
structural position, never a line number — so transaction lint-delta compares "new vs old"
without being fooled by line drift (plan §6.5 step 5).
"""

import hashlib
import os

from .. import io_utf8, parser
from ..slug import Slugger

ERROR = "ERROR"
WARN = "WARN"
INFO = "INFO"

HARD = "HARD"      # rejected regardless of baseline
DELTA = "delta"    # rejected only when newly introduced
NEVER = "never"    # reported, never blocks


class Finding:
    __slots__ = ("rule_id", "severity", "blocking", "message_zh", "position", "doc", "contract")

    def __init__(self, rule_id, severity, blocking, message_zh, position, doc, contract):
        self.rule_id = rule_id
        self.severity = severity
        self.blocking = blocking
        self.message_zh = message_zh
        self.position = position
        self.doc = doc
        self.contract = contract

    def key(self):
        h = hashlib.sha1(self.message_zh.encode("utf-8")).hexdigest()[:8]
        return (self.rule_id, self.doc, self.position, h)

    def to_dict(self):
        return {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "blocking": self.blocking,
            "message_zh": self.message_zh,
            "position": self.position,
            "doc": self.doc,
            "contract": self.contract,
        }


class Rule:
    def __init__(self, rule_id, contract, severity, blocking, scope, checker,
                 llm_only=False, needs_source=False, description=""):
        self.rule_id = rule_id
        self.contract = contract
        self.severity = severity
        self.blocking = blocking
        self.scope = tuple(scope)
        self.checker = checker
        self.llm_only = llm_only
        self.needs_source = needs_source
        self.description = description

    def to_dict(self):
        return {
            "rule_id": self.rule_id,
            "contract": self.contract,
            "severity": self.severity,
            "blocking": self.blocking,
            "scope": list(self.scope),
            "llm_only": self.llm_only,
            "needs_source": self.needs_source,
            "description": self.description,
        }


class LintContext:
    """Everything a checker needs. Sibling docs are parsed lazily and cached so
    LINK_ANCHOR_RESOLVES can compute the target's GitHub-exact anchors."""

    def __init__(self, rel_path, doc, doc_kind, doc_root=None, source_root=None,
                 overlay=None):
        self.rel_path = rel_path.replace("\\", "/")
        self.doc = doc
        self.doc_kind = doc_kind
        self.doc_root = doc_root
        self.source_root = source_root
        # In-memory overlay {absolute_path -> new_text}: docs created or edited in the
        # SAME transaction. Existence checks and anchor resolution consult it FIRST, so
        # promote/move lint can resolve links to files that are not yet on disk
        # (plan §6.5 step 3/5). Defaults to None -> unchanged behavior.
        self.overlay = {os.path.normpath(k): v for k, v in (overlay or {}).items()}
        self._anchor_cache = {}

    def make(self, rule, severity, message_zh, position):
        return Finding(rule.rule_id, severity, rule.blocking, message_zh, position,
                       self.rel_path, rule.contract)

    # --- link target resolution ---------------------------------------
    def resolve_link_path(self, link_target):
        """Absolute path of a relative link from this doc, or None if doc_root unknown."""
        if self.doc_root is None:
            return None
        doc_dir = os.path.dirname(os.path.join(self.doc_root, self.rel_path))
        return os.path.normpath(os.path.join(doc_dir, link_target))

    def link_exists(self, link_target):
        """Whether the linked file exists, consulting the overlay FIRST (a doc created or
        edited in the same transaction counts as existing). None if doc_root unknown."""
        abspath = self.resolve_link_path(link_target)
        if abspath is None:
            return None
        if os.path.normpath(abspath) in self.overlay:
            return True
        return os.path.exists(abspath)

    def target_anchors(self, link_target):
        """Set of anchors in the linked doc, or None if the file does not exist / unknown.

        Consults the overlay FIRST: if the resolved path is in the overlay, its overlay
        text is parsed for anchors (so links into a file created/edited in the same
        transaction resolve before any disk write)."""
        abspath = self.resolve_link_path(link_target)
        if abspath is None or not abspath.lower().endswith(".md"):
            return None
        if abspath in self._anchor_cache:
            return self._anchor_cache[abspath]
        norm = os.path.normpath(abspath)
        if norm in self.overlay:
            text = self.overlay[norm]
        elif not os.path.exists(abspath):
            self._anchor_cache[abspath] = None
            return None
        else:
            try:
                text = io_utf8.read_text(abspath)
            except Exception:
                self._anchor_cache[abspath] = None
                return None
        tdoc = parser.parse(abspath, text)
        slugger = Slugger()
        anchors = set()
        for h in tdoc.headings:
            anchors.add(slugger.slug(h.text))
        self._anchor_cache[abspath] = anchors
        return anchors
