"""Domain registry — read/resolve/persist `.wiki.json` (域分层设计 §5.2).

`.wiki.json` lives at the wiki base (the single known location, avoiding the
`<DOC_ROOT>` chicken-and-egg) and holds:
  domains  authoritative whitelist of domain names (always >= 1; no flat mode)
  repos    map REPO_NAME -> domain (real assignments only; never null)
"""

import json
import os

from . import io_utf8
from .errors import UnknownDomain

REGISTRY_NAME = ".wiki.json"


def registry_path(wiki_base):
    return os.path.join(wiki_base, REGISTRY_NAME)


def load_registry(wiki_base):
    """Parsed `.wiki.json` (with `domains`/`repos` keys guaranteed), or None if absent."""
    raw = io_utf8.read_text_or_none(registry_path(wiki_base))
    if raw is None:
        return None
    data = json.loads(raw)
    data.setdefault("domains", [])
    data.setdefault("repos", {})
    return data


def save_registry(wiki_base, data):
    io_utf8.write_text(registry_path(wiki_base),
                       json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def repo_name(repo_root):
    return os.path.basename(os.path.normpath(repo_root))


def parent_candidate(repo_root):
    return os.path.basename(os.path.dirname(os.path.normpath(repo_root)))
