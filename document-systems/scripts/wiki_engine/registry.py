"""Domain registry — read/resolve/persist `.wiki.json` (域分层设计 §5.2).

`.wiki.json` lives at the wiki base (the single known location, avoiding the
`<DOC_ROOT>` chicken-and-egg) and holds:
  domains  authoritative whitelist of domain names (always >= 1; no flat mode)
  repos    map REPO_NAME -> domain (real assignments only; never null)
"""

import json
import os

from . import io_utf8
from .errors import UnknownDomain, ParseError

REGISTRY_NAME = ".wiki.json"


def registry_path(wiki_base):
    return os.path.join(wiki_base, REGISTRY_NAME)


def load_registry(wiki_base):
    """Parsed `.wiki.json` (with `domains`/`repos` keys guaranteed), or None if absent."""
    raw = io_utf8.read_text_or_none(registry_path(wiki_base))
    if raw is None:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ParseError("`.wiki.json` 不是合法 JSON：{}".format(exc),
                         detail={"path": registry_path(wiki_base)})
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


def resolve(wiki_base, repo_root, set_domain=None):
    """Map REPO_ROOT to a domain (设计 §5.2). Domains are mandatory — an
    unresolvable repo raises UnknownDomain for the skill to prompt on."""
    name = repo_name(repo_root)
    reg = load_registry(wiki_base)

    if set_domain is not None:
        if reg is None:
            reg = {"domains": [], "repos": {}}
        if set_domain not in reg["domains"]:
            reg["domains"].append(set_domain)
        reg["repos"][name] = set_domain
        save_registry(wiki_base, reg)
        return {"status": "resolved", "repo": name, "domain": set_domain, "source": "set"}

    if reg is None:
        return {"status": "no_registry", "repo": name,
                "candidate": parent_candidate(repo_root)}
    if name in reg["repos"]:
        return {"status": "resolved", "repo": name,
                "domain": reg["repos"][name], "source": "repos"}
    cand = parent_candidate(repo_root)
    if cand in reg["domains"]:
        reg["repos"][name] = cand
        save_registry(wiki_base, reg)   # 写回（§5.2 ③）
        return {"status": "resolved", "repo": name, "domain": cand, "source": "parent"}
    raise UnknownDomain(
        "仓 `{}` 的父目录 `{}` 不在域白名单中，请指派已有域或新建域".format(name, cand),
        detail={"repo": name, "candidate": cand, "domains": list(reg["domains"])},
    )
