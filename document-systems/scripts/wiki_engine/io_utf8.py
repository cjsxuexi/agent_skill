"""Forced UTF-8 I/O with BOM stripping and atomic writes (plan §9.3).

All wiki content is UTF-8. Chinese paths and content are normal here, so every read
decodes UTF-8 and every write encodes UTF-8 via a temp-file + ``os.replace`` rename so
a crash never leaves a half-written document. Line endings are preserved verbatim
(no newline translation) so the byte-exact round-trip holds.
"""

import os
import tempfile

from .errors import IOFailure

_BOM = "﻿"


def read_text(path):
    """Read a file as UTF-8, stripping a leading BOM if present.

    The round-trip invariant is defined over the BOM-stripped text; writes never
    re-emit a BOM.
    """
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError as exc:
        raise IOFailure("无法读取文件：{}（{}）".format(path, exc), detail={"path": path})
    text = raw.decode("utf-8")
    if text.startswith(_BOM):
        text = text[len(_BOM):]
    return text


def write_text(path, text):
    """Atomically write ``text`` as UTF-8 (no BOM, no newline translation).

    Writes to a temp file in the same directory, then ``os.replace`` onto the target
    so readers never observe a partial file.
    """
    path = os.fspath(path)
    directory = os.path.dirname(os.path.abspath(path)) or "."
    try:
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".wiki_engine.", suffix=".tmp", dir=directory)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(text.encode("utf-8"))
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass
    except OSError as exc:
        raise IOFailure("无法写入文件：{}（{}）".format(path, exc), detail={"path": path})


def read_text_or_none(path):
    if not os.path.exists(path):
        return None
    return read_text(path)


def _silent_remove(path):
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def atomic_write_many(writes):
    """Write several files as a unit — "全写或全不写" (plan §6.5 step 6).

    ``writes`` is a list of ``(abspath, content)``. Two phases: (1) write every file to a
    temp file in its target directory, capturing each target's prior bytes; (2) ``os.replace``
    every temp onto its target. If any step fails, already-committed targets are restored from
    the captured bytes (or deleted, for files that did not previously exist) and all temps are
    removed, leaving the disk byte-identical. This is as atomic as a journal-free filesystem
    allows: phase 1 absorbs the likely failures (disk full / permission) before any commit, and
    phase-2 same-directory renames rarely fail.
    """
    staged = []  # (abspath, tmp, existed, original_bytes)
    try:
        for abspath, content in writes:
            abspath = os.fspath(abspath)
            directory = os.path.dirname(os.path.abspath(abspath)) or "."
            os.makedirs(directory, exist_ok=True)
            existed = os.path.exists(abspath)
            original = None
            if existed:
                with open(abspath, "rb") as fh:
                    original = fh.read()
            fd, tmp = tempfile.mkstemp(prefix=".wiki_engine.", suffix=".tmp", dir=directory)
            with os.fdopen(fd, "wb") as fh:
                fh.write(content.encode("utf-8"))
            staged.append((abspath, tmp, existed, original))
    except OSError as exc:
        for _abs, tmp, _e, _o in staged:
            _silent_remove(tmp)
        raise IOFailure("批量写入暂存失败（未提交任何文件）：{}".format(exc))

    committed = []  # (abspath, existed, original)
    try:
        for abspath, tmp, existed, original in staged:
            os.replace(tmp, abspath)
            committed.append((abspath, existed, original))
    except OSError as exc:
        for abspath, existed, original in reversed(committed):
            try:
                if existed:
                    with open(abspath, "wb") as fh:
                        fh.write(original)
                else:
                    _silent_remove(abspath)
            except OSError:
                pass
        for abspath, tmp, _e, _o in staged:
            _silent_remove(tmp)
        raise IOFailure("批量提交写入失败，已回滚到改动前状态：{}".format(exc))
