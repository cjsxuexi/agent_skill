"""Lint entry points (plan §6.6).

``run_lint(ctx)`` runs every rule whose scope includes the doc's DocKind and returns a
flat list of Findings. ``rule_catalog()`` returns the full rule table (id -> contract
clause -> severity -> blocking -> scope) for the ``rule-catalog`` CLI command and the
MAINTAINER §10 audit. ``has_blocking_error`` supports ``lint --strict``.
"""

from .base import LintContext, Finding, ERROR, WARN, INFO, HARD, DELTA, NEVER
from .rules import RULES


def run_lint(ctx):
    findings = []
    for rule in RULES:
        if ctx.doc_kind not in rule.scope:
            continue
        findings.extend(rule.checker(ctx))
    return findings


def rule_catalog():
    return [r.to_dict() for r in RULES]


def has_error(findings):
    return any(f.severity == ERROR for f in findings)
