"""Find document IDs in text and repair common malformed variants."""
import re

from . import config

_SEP = r"[-_\u2010-\u2015]"
_KNOWN = "|".join(sorted(config.PREFIX_TYPES, key=len, reverse=True))

_ID_RE = re.compile(
    r"(?<![A-Za-z0-9])"
    r"((?i:" + _KNOWN + r")|[A-Z]{2,6})"
    r"(?:" + _SEP + r"([A-Za-z]{2,6}))?"
    + _SEP + r"(\d{1,6})"
    r"(?![A-Za-z0-9])(?!" + _SEP + r"\d)"
)

_REVISION_RE = re.compile(
    r"[\s,(\-_\u2010-\u2015]*(?i:rev(?:ision)?|version|ver|issue|v)\.?\s*"
    r"([0-9]{1,3}[A-Za-z]?|[A-Z])\b"
)

_SECTION_RE = re.compile(
    r"\s*[,(]?\s*(?:section|sec\.?|\u00a7|clause|step|paragraph|para\.?)\s*"
    r"([0-9][0-9A-Za-z.]*)",
    re.IGNORECASE,
)


def doc_type_for_prefix(prefix):
    """Return the document type for a prefix such as 'SOP', or 'document'."""
    return config.PREFIX_TYPES.get(prefix.upper(), "document")


def _canonical(prefix, mid, number):
    if config.PAD_NUMBERS_TO and len(number) < config.PAD_NUMBERS_TO:
        number = number.zfill(config.PAD_NUMBERS_TO)
    parts = [prefix.upper()]
    if mid:
        parts.append(mid.upper())
    parts.append(number)
    return "-".join(parts)


def normalise_id(text):
    """Return the canonical form of a single ID string, or None if it is not an ID."""
    found = find_ids(text.strip())
    if len(found) == 1 and found[0]["start"] == 0 and found[0]["id_end"] == len(text.strip()):
        return found[0]["canonical"]
    return None


def find_ids(text):
    """Return every accepted ID in text.

    Each item has: start, end, id_end, raw, canonical, prefix, doc_type, confidence,
    revision, section. 'end' includes any revision or section text that follows the ID.
    Items skipped because their prefix is on the stop-list are counted in the
    'stoplisted' key of the second return value of find_ids_with_stats.
    """
    return find_ids_with_stats(text)[0]


def find_ids_with_stats(text):
    results = []
    stoplisted = 0
    for match in _ID_RE.finditer(text):
        prefix, mid, number = match.group(1), match.group(2), match.group(3)
        prefix_up = prefix.upper()
        if prefix_up in config.PREFIX_STOPLIST:
            stoplisted += 1
            continue
        if set(number) == {"0"} or (mid and set(mid.upper()) == {"X"}):
            stoplisted += 1  # template placeholder such as SOP-XXX-000
            continue
        known = prefix_up in config.PREFIX_TYPES
        if not known:
            if not config.ACCEPT_UNLISTED_PREFIXES:
                continue
            if len(number) < config.MIN_DIGITS_UNLISTED:
                continue
            if mid and not mid.isupper():
                continue
        raw = match.group(0)
        canonical = _canonical(prefix, mid, number)
        end = match.end()
        revision = None
        section = None
        rev_match = _REVISION_RE.match(text, end)
        if rev_match:
            revision = rev_match.group(1)
            end = rev_match.end()
        sec_match = _SECTION_RE.match(text, end)
        if sec_match:
            section = sec_match.group(1).rstrip(".")
            end = sec_match.end()
        results.append({
            "start": match.start(),
            "id_end": match.end(),
            "end": end,
            "raw": raw,
            "canonical": canonical,
            "prefix": prefix_up,
            "doc_type": doc_type_for_prefix(prefix_up),
            "confidence": "exact" if raw == canonical else "normalised",
            "revision": revision,
            "section": section,
        })
    return results, stoplisted
