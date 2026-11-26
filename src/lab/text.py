"""Small text-normalisation helpers shared by every module."""

import re
import unicodedata

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def normalize_text(value: str) -> str:
    """Return ``value`` in NFC form, control characters removed, whitespace collapsed.

    >>> normalize_text("  Ada \\t  Lovelace\\n")
    'Ada Lovelace'
    """
    value = unicodedata.normalize("NFC", value)
    value = _CONTROL_CHARS.sub(" ", value)
    return " ".join(value.split())
