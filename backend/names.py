"""
Name normalisation for spotting duplicate professors.

normalize_name: "Dr. Alex Lim", "alex lim", "Assoc Prof Alex-Lim" -> "alexlim"  (stored as name_key)
name_words:     "Dr. Alex Lim"                                    -> "alex lim" (for word-order-blind matching)
"""
import re
import unicodedata

# Titles people put in front of a name. Removed repeatedly, so "Assoc Prof Dr" all go.
HONORIFICS = (
    "professor", "prof", "associate", "assoc", "assistant", "asst", "a/p",
    "adjunct", "adj", "emeritus", "dr", "mr", "mrs", "ms", "mdm",
)
# Ends with a dot ("Dr.Tan"), whitespace, or the end; so "Drew" is left alone
_HONORIFIC = re.compile(
    r"^(?:" + "|".join(re.escape(h) for h in HONORIFICS) + r")(?:\.\s*|\s+|$)"
)
_NOT_ALNUM = re.compile(r"[^a-z0-9]+")


def _strip_honorifics(name: str) -> tuple[str, str]:
    """Returns (folded original, folded without leading titles)."""
    # NFKD splits "é" into "e" + a combining accent; drop the accent, keep the "e"
    decomposed = unicodedata.normalize("NFKD", name)
    original = "".join(c for c in decomposed if not unicodedata.combining(c)).lower().strip()
    text = original
    while True:
        stripped = _HONORIFIC.sub("", text, count=1).lstrip()
        if stripped == text:
            return original, text
        text = stripped


def normalize_name(name: str) -> str:
    original, text = _strip_honorifics(name)
    # A "name" that is only a title ("Dr") keeps it rather than becoming empty
    return _NOT_ALNUM.sub("", text) or _NOT_ALNUM.sub("", original)


def name_words(name: str) -> str:
    original, text = _strip_honorifics(name)
    words = _NOT_ALNUM.sub(" ", text).strip()
    return words or _NOT_ALNUM.sub(" ", original).strip()
