"""Domain registry — read/resolve/persist `.wiki.json` (域分层设计 §5.2).

Sources are laid out as `<WIKI scope>/<DOMAIN>/<REPO>`, so a repo's **parent
folder name IS its domain**. Resolution is therefore a pure function of the repo
path plus the domain whitelist — there is no repo→domain map to keep in sync, and
two same-named repos under different domain folders (e.g. `PSA_FMS/fms-server` vs
`NP_FMS/fms-server`) can never collide.

`.wiki.json` lives at the wiki base (the single known location, avoiding the
`<DOC_ROOT>` chicken-and-egg) and holds just:
  domains  authoritative whitelist of domain names (always >= 1; no flat mode).
           A typo/accident guard: a parent folder absent from the whitelist
           raises UnknownDomain so the skill confirms before a stray folder
           silently becomes a phantom domain.

(A legacy `repos` map keyed by basename used to live here; keying by basename
broke same-named repos across domains, so it is obsolete. It is dropped on load
so the next save rewrites a clean `{domains}` registry.)
"""

import json
import os

from . import io_utf8
from .errors import UnknownDomain, ParseError

REGISTRY_NAME = ".wiki.json"


def registry_path(wiki_base):
    return os.path.join(wiki_base, REGISTRY_NAME)


def load_registry(wiki_base):
    """Parsed `.wiki.json` (with `domains` guaranteed), or None if absent.

    Any legacy basename `repos` map is dropped here, so a registry written before
    the parent-folder model is silently migrated to the clean `{domains}` shape on
    the next save."""
    raw = io_utf8.read_text_or_none(registry_path(wiki_base))
    if raw is None:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ParseError("`.wiki.json` 不是合法 JSON：{}".format(exc),
                         detail={"path": registry_path(wiki_base)})
    data.setdefault("domains", [])
    data.pop("repos", None)   # obsolete basename map — drop (migrate on next save)
    return data


def save_registry(wiki_base, data):
    io_utf8.write_text(registry_path(wiki_base),
                       json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def repo_name(repo_root):
    return os.path.basename(os.path.normpath(repo_root))


def parent_candidate(repo_root):
    return os.path.basename(os.path.dirname(os.path.normpath(repo_root)))


def resolve(wiki_base, repo_root, set_domain=None):
    """Map REPO_ROOT to a domain (设计 §5.2): the domain is the repo's parent
    folder name. Domains are mandatory — a parent folder absent from the whitelist
    raises UnknownDomain for the skill to prompt on (新建域 / 指派已有域).

    `--set <d>` only adds `<d>` to the whitelist; there is no repo→domain map, so
    registering one repo never overwrites a same-named repo in another domain.
    Resolution itself persists nothing — it is a pure function of (parent folder,
    whitelist)."""
    name = repo_name(repo_root)
    cand = parent_candidate(repo_root)
    reg = load_registry(wiki_base)

    if set_domain is not None:
        if reg is None:
            reg = {"domains": []}
        if set_domain not in reg["domains"]:
            reg["domains"].append(set_domain)
        save_registry(wiki_base, reg)
        return {"status": "resolved", "repo": name, "domain": set_domain, "source": "set"}

    if reg is None:
        return {"status": "no_registry", "repo": name, "candidate": cand}
    if cand in reg["domains"]:
        return {"status": "resolved", "repo": name, "domain": cand, "source": "parent"}
    raise UnknownDomain(
        "仓 `{}` 的父目录 `{}` 不在域白名单中，请指派已有域或新建域".format(name, cand),
        detail={"repo": name, "candidate": cand, "domains": list(reg["domains"])},
    )
