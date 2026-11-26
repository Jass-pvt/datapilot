"""Exception types whose messages are safe to show to end users.

Every ``LabError`` message is written by us and never contains raw input values,
file system paths of internal modules, SQL text or stack traces. The CLI prints
only these messages; anything else becomes a generic "internal error".
"""


class LabError(Exception):
    """Base class for expected, user-presentable errors."""


class ConfigError(LabError):
    """Invalid arguments or settings supplied by the caller."""


class ApiError(LabError):
    """An external API could not be used (network, HTTP status, invalid body)."""


class MalformedResponseError(LabError):
    """The response had the wrong overall structure (not per-record problems)."""


class InputError(LabError):
    """An input file is unusable (missing, empty, too large, wrong encoding)."""


class ImportFailedError(LabError):
    """The database rejected an import; the transaction was rolled back."""
