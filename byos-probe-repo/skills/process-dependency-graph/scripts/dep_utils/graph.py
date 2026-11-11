"""Load per-page records and merge them into one dependency graph."""
import glob
import json
import os

PAGE_RECORD_PATTERN = "*dependency*.json"


def _collect_strings(value, found):
    if isinstance(value, str):
        found.append(value)
    elif isinstance(value, dict):
        for item in value.values():
            _collect_strings(item, found)
    elif isinstance(value, list):
        for item in value:
            _collect_strings(item, found)


def _try_load_record(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    if isinstance(data, dict) and "doc_id" in data and isinstance(data.get("refs"), list):
        return data
    return None


def load_records(manifest_path):
    """Return (records, warnings).

    The shape of the manifest the platform passes is not documented, so this accepts a list of
    paths, a list of objects with path-like values, an object wrapping either, or a plain text
    list of paths. If nothing usable is found it falls back to scanning nearby directories.
    """
    warnings = []
    manifest_dir = os.path.dirname(os.path.abspath(manifest_path))
    try:
        with open(manifest_path, "r", encoding="utf-8", errors="replace") as handle:
            raw = handle.read()
    except OSError as error:
        raw = ""
        warnings.append("manifest could not be read: " + str(error))

    candidates = []
    try:
        _collect_strings(json.loads(raw), candidates)
    except ValueError:
        candidates = [line.strip() for line in raw.splitlines() if line.strip()]

    records, seen = [], set()

    def add(path):
        real = os.path.realpath(path)
        if real in seen or real == os.path.realpath(manifest_path):
            return
        record = _try_load_record(path)
        if record is not None:
            seen.add(real)
            records.append(record)

    for candidate in candidates:
        for path in (candidate, os.path.join(manifest_dir, candidate),
                     os.path.join(manifest_dir, os.path.basename(candidate))):
            if os.path.isfile(path):
                add(path)
                break

    listed = len(records)
    if not records:
        warnings.append("no page records found through the manifest; scanned nearby folders instead")
        for folder in (manifest_dir, os.getcwd()):
            for path in sorted(glob.glob(os.path.join(folder, PAGE_RECORD_PATTERN))):
                add(path)
    elif listed < len([c for c in candidates if c.lower().endswith(".json")]):
        warnings.append("some paths in the manifest could not be read as page records")
    return records, warnings


def build_graph(records):
    """Merge page records into nodes and edges. Edges point from dependent to dependency."""
    nodes, edges, warnings = {}, {}, []
    stats = {
        "pages": len(records), "pages_with_id": 0, "id_sources": {}, "pages_without_doc_refs": 0,
        "truncated_pages": 0, "normalised_refs": 0, "self_references": 0,
        "change_log_references": 0, "lineage_references": 0, "stoplisted_ids": 0,
        "duplicate_ids": [], "normalisations": [],
    }

    for record in sorted(records, key=lambda r: str(r.get("doc_id"))):
        doc_id = str(record.get("doc_id"))
        source = record.get("doc_id_source", "unknown")
        stats["id_sources"][source] = stats["id_sources"].get(source, 0) + 1
        if source != "slug-fallback":
            stats["pages_with_id"] += 1
        if record.get("truncated_suspected"):
            stats["truncated_pages"] += 1
        for key in ("self_references", "change_log_references", "lineage_references", "stoplisted_ids"):
            stats[key] += int(record.get("ignored", {}).get(key, 0))
        if doc_id in nodes:
            stats["duplicate_ids"].append(doc_id)
            warnings.append("document ID " + doc_id + " appears on more than one page; merged into one node")
            nodes[doc_id]["pages"] += 1
            continue
        nodes[doc_id] = {
            "id": doc_id, "kind": "document", "doc_type": record.get("doc_type", "document"),
            "title": record.get("title"), "pages": 1, "no_id": source == "slug-fallback",
            "truncated": bool(record.get("truncated_suspected")),
        }
        for message in record.get("warnings", []):
            warnings.append(doc_id + ": " + message)

    for record in sorted(records, key=lambda r: str(r.get("doc_id"))):
        own = str(record.get("doc_id"))
        has_doc_ref = False
        for ref in record.get("refs", []):
            target, kind = ref.get("target"), ref.get("kind", "document")
            if not target or target == own:
                continue
            if kind == "system":
                if target not in nodes:
                    nodes[target] = {"id": target, "kind": "system", "doc_type": "system",
                                     "title": None, "pages": 0, "no_id": False, "truncated": False}
                source_id, dest_id = own, target
            else:
                has_doc_ref = True
                if target not in nodes:
                    nodes[target] = {"id": target, "kind": "unresolved", "doc_type": kind,
                                     "title": None, "pages": 0, "no_id": False, "truncated": False}
                if ref.get("relation") == "depended_on_by":
                    source_id, dest_id = target, own
                else:
                    source_id, dest_id = own, target
            if ref.get("confidence") == "normalised":
                stats["normalised_refs"] += 1
                stats["normalisations"].append((ref.get("raw"), target, own))
            edge = edges.get((source_id, dest_id))
            location = {"page": own, "line": ref.get("line"), "section": ref.get("section"),
                        "context": ref.get("context"), "mentions": int(ref.get("mentions", 1))}
            if edge is None:
                edges[(source_id, dest_id)] = {
                    "src": source_id, "dst": dest_id, "mentions": int(ref.get("mentions", 1)),
                    "confidence": ref.get("confidence", "exact"), "where": [location],
                }
            else:
                edge["mentions"] += int(ref.get("mentions", 1))
                if edge["confidence"] != "exact" and ref.get("confidence") == "exact":
                    edge["confidence"] = "exact"
                if len(edge["where"]) < 3:
                    edge["where"].append(location)
        if not has_doc_ref:
            stats["pages_without_doc_refs"] += 1

    return {"nodes": nodes, "edges": edges, "warnings": warnings, "stats": stats}
