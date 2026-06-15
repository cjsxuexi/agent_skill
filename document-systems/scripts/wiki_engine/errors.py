"""Exit-code model (plan §6.8) and the engine's typed error hierarchy.

Exit codes:
    0  success
    2  usage error (bad CLI invocation)
    3  transaction rejected (lint delta or a HARD rule)
    4  addressing failure (E_ADDR_*)
    5  coupling missing (E_COUPLING_MISSING)
    6  stale replacement string (E_MATCH_STALE)
    7  parse failure
    8  IO failure
    9  source root missing (only under --require-source)

``lint`` itself exits 0 even with findings (findings are the product); under
``--strict`` it exits 3 when any ERROR finding is present.
"""

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_REJECTED = 3
EXIT_ADDR = 4
EXIT_COUPLING = 5
EXIT_MATCH_STALE = 6
EXIT_PARSE = 7
EXIT_IO = 8
EXIT_NO_SOURCE = 9


class EngineError(Exception):
    """Base for all engine errors. ``code`` is the English machine code,
    ``message_zh`` the Chinese user-facing message, ``exit_code`` the process code."""

    code = "E_ENGINE"
    exit_code = EXIT_USAGE

    def __init__(self, message_zh, code=None, exit_code=None, detail=None):
        super().__init__(message_zh)
        self.message_zh = message_zh
        if code is not None:
            self.code = code
        if exit_code is not None:
            self.exit_code = exit_code
        self.detail = detail or {}

    def to_dict(self):
        d = {"code": self.code, "message_zh": self.message_zh}
        if self.detail:
            d["detail"] = self.detail
        return d


class UsageError(EngineError):
    code = "E_USAGE"
    exit_code = EXIT_USAGE


class ParseError(EngineError):
    code = "E_PARSE"
    exit_code = EXIT_PARSE


class IOFailure(EngineError):
    code = "E_IO"
    exit_code = EXIT_IO


class AddressError(EngineError):
    code = "E_ADDR"
    exit_code = EXIT_ADDR


class AddressNotFound(AddressError):
    code = "E_ADDR_NOTFOUND"


class AddressAmbiguous(AddressError):
    code = "E_ADDR_AMBIGUOUS"


class CouplingMissing(EngineError):
    code = "E_COUPLING_MISSING"
    exit_code = EXIT_COUPLING


class MatchStale(EngineError):
    code = "E_MATCH_STALE"
    exit_code = EXIT_MATCH_STALE


class TransactionRejected(EngineError):
    code = "E_REJECTED"
    exit_code = EXIT_REJECTED


class SourceRootMissing(EngineError):
    code = "E_NO_SOURCE"
    exit_code = EXIT_NO_SOURCE


class RootEdgeDangling(EngineError):
    code = "E_ROOT_EDGE_DANGLING"
    exit_code = EXIT_REJECTED
