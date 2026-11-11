"""Turn one wiki page (markdown text) into a dependency record."""
import re

from . import config
from .idparse import find_ids_with_stats

SCHEMA_VERSION = 1

_FM_ID_KEYS = (
    "doc_id", "docid", "id", "document_id", "document_number", "doc_number",
    "document_no", "doc_no", "number", "code",
)
_HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
_LABEL_RE = re.compile(
    r"(?i)^[\s|*_>-]*(?:(?:document|doc)\.?\s*(?:id|no\.?|number|#)|id)\s*\**\s*[:|=]"
)
_FILLER_RE = re.compile(r"[\s:,\-\u2013\u2014/&]*(?:(?:and|or)[\s,]*)?")
_SENTENCE_END_RE = re.compile(r"[.;!?](?=\s|$)")
_LIST_MARKER_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")


def _phrase_regex(phrases):
    parts = []
    for phrase in sorted(phrases, key=len, reverse=True):
        parts.append(r"\s+".join(re.escape(word) for word in phrase.split()))
    return re.compile(r"(?<![A-Za-z])(?:" + "|".join(parts) + r")(?![A-Za-z])", re.IGNORECASE)


_DEP_BY_RE = _phrase_regex(config.DEPENDED_ON_BY_PHRASES)
_LINEAGE_RE = _phrase_regex(config.LINEAGE_PHRASES)

_SYSTEM_ALIASES = {alias.lower(): canonical for alias, canonical in config.SYSTEMS.items()}
_SYSTEM_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:"
    + "|".join(re.escape(a) for a in sorted(config.SYSTEMS, key=len, reverse=True))
    + r")(?![A-Za-z0-9])",
    re.IGNORECASE,
)


def _slug(text):
    slug = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")
    return slug[:60].upper() or "UNNAMED"


def _parse_frontmatter(lines):
    """Return (dict, index of first line after the frontmatter)."""
    if not lines or lines[0].strip() != "---":
        return {}, 0
    values = {}
    for index in range(1, len(lines)):
        stripped = lines[index].strip()
        if stripped in ("---", "..."):
            return values, index + 1
        if ":" in stripped:
            key, _, value = stripped.partition(":")
            values[key.strip().lower()] = value.strip().strip("\"'")
    return {}, 0


def _heading_info(line):
    """Return (level, text) if the line acts as a heading, else None."""
    match = _HEADING_RE.match(line)
    if match:
        return len(match.group(1)), match.group(2)
    plain = re.sub(r"^[\s*_#]+|[\s*_:#]+$", "", line).lower()
    if plain and plain in _ZONE_PHRASES:
        return 7, plain
    return None


_CHANGE_LOG = tuple(h.lower() for h in config.CHANGE_LOG_HEADINGS)
_RELATED = tuple(h.lower() for h in config.RELATED_HEADINGS)
_DEP_BY_HEADINGS = tuple(p.lower() for p in config.DEPENDED_ON_BY_PHRASES)
_ZONE_PHRASES = set(_CHANGE_LOG) | set(_RELATED) | set(_DEP_BY_HEADINGS)


def _zone_for_heading(text):
    """Return (zone name, default relation) if the heading opens a special zone."""
    lowered = text.lower().strip(" :*_#")
    if lowered.startswith(_CHANGE_LOG):
        return "change_log", "depends_on"
    if lowered.startswith(_DEP_BY_HEADINGS):
        return "related", "depended_on_by"
    if lowered.startswith(_RELATED):
        return "related", "depends_on"
    return None


def _find_own_id(lines, frontmatter, body_start):
    """Return (id info dict or None, source, title_text)."""
    title_text = None
    for line in lines[body_start:]:
        info = _HEADING_RE.match(line)
        if info and len(info.group(1)) == 1:
            title_text = info.group(2)
            break

    for key in _FM_ID_KEYS:
        value = frontmatter.get(key)
        if value:
            found = find_ids_with_stats(value)[0]
            if found:
                return found[0], "frontmatter", title_text or frontmatter.get("title")

    fm_title = frontmatter.get("title")
    if fm_title:
        found = find_ids_with_stats(fm_title)[0]
        if found:
            return found[0], "frontmatter-title", title_text or fm_title

    if title_text:
        found = find_ids_with_stats(title_text)[0]
        if found:
            return found[0], "h1", title_text

    window = lines[body_start:body_start + config.OWN_ID_SEARCH_LINES]
    for line in window:
        if _LABEL_RE.search(line):
            found = find_ids_with_stats(line)[0]
            if found:
                return found[0], "label", title_text

    # Last resort: a short first line that looks like a title (a long first line is more likely
    # a sentence that cites another document).
    for line in window:
        if not line.strip():
            continue
        if len(line.split()) <= 12:
            found = find_ids_with_stats(line)[0]
            if found:
                return found[0], "first-line", title_text
        break

    return None, "slug-fallback", title_text


def _clean_title(title_text, own):
    if not title_text:
        return None
    if own:
        title_text = title_text.replace(own["raw"], "", 1)
    return title_text.strip(" \t-\u2013\u2014:_|") or None


def _first_text_line(lines, body_start):
    for line in lines[body_start:]:
        if line.strip():
            return line.strip().lstrip("#").strip()
    return None


def _sentence_spans(line):
    spans = []
    start = 0
    for match in _SENTENCE_END_RE.finditer(line):
        spans.append((start, match.end()))
        start = match.end()
    spans.append((start, len(line)))
    return spans


def _relations_for_line(line, ids, default_relation):
    """Assign a relation ('depends_on', 'depended_on_by', 'lineage') to each ID in the line."""
    relations = [default_relation] * len(ids)
    for sentence_start, sentence_end in _sentence_spans(line):
        phrases = []
        for regex, relation in ((_DEP_BY_RE, "depended_on_by"), (_LINEAGE_RE, "lineage")):
            for match in regex.finditer(line, sentence_start, sentence_end):
                phrases.append((match.start(), match.end(), relation))
        phrases.sort()
        for _, phrase_end, relation in phrases:
            anchor = phrase_end
            for index, item in enumerate(ids):
                if item["start"] < anchor or item["start"] >= sentence_end:
                    continue
                if _FILLER_RE.fullmatch(line[anchor:item["start"]]):
                    relations[index] = relation
                    anchor = item["end"]
                else:
                    break
    return relations


def _sentence_for(line, position):
    for start, end in _sentence_spans(line):
        if start <= position < end or (position == end and end == len(line)):
            snippet = line[start:end]
            break
    else:
        snippet = line
    snippet = _LIST_MARKER_RE.sub("", snippet.strip()).strip()
    if len(snippet) > config.CONTEXT_CHARS:
        snippet = snippet[:config.CONTEXT_CHARS - 3].rstrip() + "..."
    return snippet


def parse_page(text, fallback_name="page"):
    """Parse one page and return its dependency record (a plain dict)."""
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    warnings = []
    if not text.strip():
        warnings.append("page is empty")

    frontmatter, body_start = _parse_frontmatter(lines)
    own, own_source, title_text = _find_own_id(lines, frontmatter, body_start)

    if own:
        own_id = own["canonical"]
        doc_type = own["doc_type"]
    else:
        base = title_text or frontmatter.get("title") or _first_text_line(lines, body_start) or fallback_name
        own_id = "NOID-" + _slug(base)
        doc_type = "document"
        title_text = title_text or base
        warnings.append("no document ID found; placeholder " + own_id + " used")

    title = _clean_title(title_text or frontmatter.get("title"), own)
    truncated = len(text) >= config.TRUNCATION_SUSPECT_CHARS
    if truncated:
        warnings.append("page is about the wiki length limit; references near the end may be missing")

    ignored = {"self_references": 0, "change_log_references": 0, "lineage_references": 0, "stoplisted_ids": 0}
    lineage = set()
    refs = {}

    own_seen = False
    zone, zone_level, zone_relation = "body", 0, "depends_on"
    for line_number, line in enumerate(lines, start=1):
        if line_number <= body_start or not line.strip():
            continue

        heading = _heading_info(line)
        if heading:
            level, heading_text = heading
            special = _zone_for_heading(heading_text)
            if special:
                zone, zone_relation = special
                zone_level = level
            elif zone != "body" and level <= zone_level:
                zone, zone_level, zone_relation = "body", 0, "depends_on"

        ids, stoplisted = find_ids_with_stats(line)
        ignored["stoplisted_ids"] += stoplisted
        relations = _relations_for_line(line, ids, zone_relation)

        for item, relation in zip(ids, relations):
            if item["canonical"] == own_id:
                # The first mention is the page naming itself; only later ones are self-references.
                if own_seen:
                    ignored["self_references"] += 1
                own_seen = True
                continue
            if zone == "change_log":
                ignored["change_log_references"] += 1
                continue
            if relation == "lineage":
                ignored["lineage_references"] += 1
                lineage.add(item["canonical"])
                continue
            key = (item["canonical"], relation, zone)
            entry = refs.get(key)
            if entry is None:
                refs[key] = {
                    "target": item["canonical"],
                    "kind": item["doc_type"],
                    "relation": relation,
                    "zone": zone,
                    "confidence": item["confidence"],
                    "raw": item["raw"],
                    "line": line_number,
                    "section": item["section"],
                    "revision": item["revision"],
                    "context": _sentence_for(line, item["start"]),
                    "mentions": 1,
                }
            else:
                entry["mentions"] += 1
                if entry["confidence"] != "exact" and item["confidence"] == "exact":
                    entry["confidence"] = "exact"
                if entry["section"] is None and item["section"]:
                    entry["section"] = item["section"]

        if zone != "change_log":
            masked = line
            for item in ids:
                masked = masked[:item["start"]] + " " * (item["id_end"] - item["start"]) + masked[item["id_end"]:]
            for match in _SYSTEM_RE.finditer(masked):
                canonical = _SYSTEM_ALIASES.get(match.group(0).lower(), match.group(0))
                key = (canonical, "depends_on", zone)
                entry = refs.get(key)
                if entry is None:
                    refs[key] = {
                        "target": canonical,
                        "kind": "system",
                        "relation": "depends_on",
                        "zone": zone,
                        "confidence": "exact",
                        "raw": match.group(0),
                        "line": line_number,
                        "section": None,
                        "revision": None,
                        "context": _sentence_for(line, match.start()),
                        "mentions": 1,
                    }
                else:
                    entry["mentions"] += 1

    ordered = [refs[key] for key in sorted(refs, key=lambda k: (k[2], k[0], k[1]))]
    return {
        "schema_version": SCHEMA_VERSION,
        "doc_id": own_id,
        "doc_id_source": own_source,
        "doc_type": doc_type,
        "title": title,
        "chars": len(text),
        "truncated_suspected": truncated,
        "refs": ordered,
        "lineage": sorted(lineage),
        "ignored": ignored,
        "warnings": warnings,
    }
