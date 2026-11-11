"""Render the dependency report, Mermaid diagram and graph JSON."""
import json

from . import config


def _cell(text):
    return str(text if text is not None else "").replace("|", "\\|").replace("\n", " ").strip()


def _code(text):
    return "`" + str(text) + "`"


def _join(items, limit):
    items = list(items)
    shown = ", ".join(_code(i) for i in items[:limit])
    if len(items) > limit:
        shown += " (+" + str(len(items) - limit) + " more)"
    return shown or "none"


def _n(count, noun):
    """'1 document' / '3 documents'."""
    return str(count) + " " + noun + ("" if count == 1 else "s")


def _short(text, limit=60):
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit - 3].rstrip() + "..."


def _evidence_rows(graph):
    """Return deterministic, reviewable evidence for each retained graph edge."""
    rows = []
    for (src, dst), edge in sorted(graph["edges"].items()):
        for location in edge.get("where") or [{}]:
            rows.append({
                "from": src, "to": dst, "edge_mentions": edge.get("mentions", 0),
                "page_mentions": location.get("mentions", edge.get("mentions", 0)),
                "confidence": edge.get("confidence", "exact"),
                "page": location.get("page"), "line": location.get("line"),
                "section": location.get("section"), "context": location.get("context"),
            })
    return rows


def diagram_nodes(graph, analysis):
    """Pick the nodes and edges shown in the diagram: top documents plus a few neighbours."""
    nodes, metrics = graph["nodes"], analysis["metrics"]
    chosen = [d for d in analysis["ranking"]
              if metrics[d]["dependents"] + metrics[d]["dependencies"] > 0][:config.MERMAID_TOP_DOCS]
    chosen_set = set(chosen)
    extra_counts = {}
    for (src, dst) in graph["edges"]:
        for near, far in ((src, dst), (dst, src)):
            if near in chosen_set and far not in chosen_set and nodes[far]["kind"] != "document":
                extra_counts[far] = extra_counts.get(far, 0) + 1
    extras = sorted(extra_counts, key=lambda n: (-extra_counts[n], n))[:config.MERMAID_MAX_EXTRA_NODES]
    selected = sorted(chosen_set | set(extras))
    selected_set = set(selected)
    edges = sorted((s, d) for (s, d) in graph["edges"] if s in selected_set and d in selected_set)
    return selected, edges


def mermaid_text(graph, analysis, selected, edges):
    nodes, metrics = graph["nodes"], analysis["metrics"]
    names = {node_id: "n" + str(i) for i, node_id in enumerate(selected)}
    lines = ["flowchart LR"]
    for node_id in selected:
        label = node_id.replace('"', "'")
        if nodes[node_id]["kind"] == "system":
            lines.append("  " + names[node_id] + '{{"' + label + '"}}')
        else:
            lines.append("  " + names[node_id] + '["' + label + '"]')
    for src, dst in edges:
        lines.append("  " + names[src] + " --> " + names[dst])
    lines.append("  classDef cycle fill:#ffe0e0,stroke:#c0392b")
    lines.append("  classDef unresolved stroke-dasharray: 5 5,fill:#f4f4f4")
    lines.append("  classDef system fill:#e8f0ff,stroke:#3b82d4")
    for css, test in (("cycle", lambda n: metrics[n]["cycle"] is not None),
                      ("unresolved", lambda n: nodes[n]["kind"] == "unresolved"),
                      ("system", lambda n: nodes[n]["kind"] == "system")):
        members = [names[n] for n in selected if test(n)]
        if members:
            lines.append("  class " + ",".join(members) + " " + css)
    return "\n".join(lines)


def graph_json(graph, analysis, selected=None):
    nodes, metrics = graph["nodes"], analysis["metrics"]
    keep = set(selected) if selected is not None else set(nodes)
    node_list = []
    for node_id in sorted(keep):
        node = nodes[node_id]
        node_list.append({
            "id": node_id, "kind": node["kind"], "type": node["doc_type"], "title": node["title"],
            "dependents": metrics[node_id]["dependents"], "dependencies": metrics[node_id]["dependencies"],
            "blast_radius": metrics[node_id]["blast"], "cycle": metrics[node_id]["cycle"],
            "tier": metrics[node_id]["tier"],
        })
    edge_list = []
    for (src, dst), edge in sorted(graph["edges"].items()):
        if src in keep and dst in keep:
            edge_list.append({"from": src, "to": dst, "mentions": edge["mentions"],
                              "confidence": edge["confidence"]})
    return {"nodes": node_list, "edges": edge_list}


def _summary(graph, analysis):
    nodes, metrics = graph["nodes"], analysis["metrics"]
    docs = [n for n in nodes if nodes[n]["kind"] == "document"]
    doc_edges = [e for e in graph["edges"] if nodes[e[0]]["kind"] != "system" and nodes[e[1]]["kind"] != "system"
                 and nodes[e[0]]["kind"] == "document" and nodes[e[1]]["kind"] == "document"]
    lines = []
    lines.append("- **Scope:** " + _n(len(docs), "document") + " analysed, " + _n(len(doc_edges), "link") +
                 " between them, " + _n(len(analysis["systems"]), "system") + " referenced.")
    top = [d for d in analysis["ranking"] if metrics[d]["blast"] > 0][:3]
    if top:
        parts = ["changing " + _code(d) + " may affect " + _n(metrics[d]["blast"], "document") + " (" +
                 str(metrics[d]["dependents"]) + " cite" + ("s" if metrics[d]["dependents"] == 1 else "") +
                 " it directly)" for d in top]
        lines.append("- **Highest risk:** " + "; ".join(parts) + ".")
    else:
        lines.append("- **Highest risk:** no document is cited by another, so no change spreads.")
    if analysis["cycles"]:
        names = "; ".join("{" + ", ".join(c["members"][:5]) + (", ..." if len(c["members"]) > 5 else "") + "}"
                          for c in analysis["cycles"][:3])
        lines.append("- **Cycles needing a human decision:** " + _n(len(analysis["cycles"]), "cycle") +
                     " found, for example " + names + ". These documents depend on each other, so none can be treated as the starting point.")
    else:
        lines.append("- **Cycles:** none found.")
    if analysis["unresolved"]:
        lines.append("- **Missing documents:** " + _n(len(analysis["unresolved"]), "document") +
                     " referenced but not in the corpus, most cited first: " +
                     _join([u["id"] for u in analysis["unresolved"]], 3) + ".")
    else:
        lines.append("- **Missing documents:** none; every cited document is in the corpus.")
    if analysis["tiers"]:
        first = analysis["tiers"][0]
        lines.append("- **Suggested order:** " + _n(len(analysis["tiers"]), "tier") + ". Start with tier 0 (" +
                     _n(sum(len(u) for u in first), "document") + " depending on no other document in the corpus).")
    stats = graph["stats"]
    thin = stats["pages"] > 0 and (stats["pages"] - stats["pages_without_doc_refs"]) * 10 < stats["pages"] * 3
    if not graph["edges"]:
        lines.append("- **Confidence:** no references were found. Check that the pages carry document IDs and that the ID pattern in `config.py` fits them.")
    elif thin:
        lines.append("- **Confidence:** the graph is thin. Fewer than 30% of pages cite another document by ID, so it understates the real dependencies.")
    return lines


def render_report(graph, analysis):
    nodes, metrics, stats = graph["nodes"], analysis["metrics"], graph["stats"]
    out = ["# Process dependency graph", ""]
    out.append("Arrows run from a document to the documents it depends on. Blast radius is the number of documents that depend on a document directly or through other documents.")
    out += ["", "## Summary", ""] + _summary(graph, analysis)

    out += ["", "## Most depended-on documents", ""]
    out.append("| Rank | Document | Type | Title | Direct dependents | Blast radius | Direct dependencies | Cycle | Tier |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    for rank, doc in enumerate(analysis["ranking"][:config.TOP_RANKED_ROWS], start=1):
        m = metrics[doc]
        out.append("| " + " | ".join([
            str(rank), _code(doc), _cell(nodes[doc]["doc_type"]), _cell(_short(nodes[doc]["title"])),
            str(m["dependents"]), str(m["blast"]), str(m["dependencies"]),
            ("yes (" + str(m["cycle"]) + ")") if m["cycle"] else "no",
            str(m["tier"]) if m["tier"] is not None else "-"]) + " |")
    if len(analysis["ranking"]) > config.TOP_RANKED_ROWS:
        out.append("")
        out.append("Showing " + str(config.TOP_RANKED_ROWS) + " of " + str(len(analysis["ranking"])) + " documents.")

    touched = [d for d in analysis["ranking"] if metrics[d]["blast"] > 0][:10]
    if touched:
        out += ["", "## What a change touches", ""]
        for doc in touched:
            out.append("- " + _code(doc) + " touches " + _n(metrics[doc]["blast"], "document") + ". Cited directly by: " +
                       _join([d for d in analysis["in_adj"][doc] if nodes[d]["kind"] == "document"], 8) + ".")

    out += ["", "## Cycles", ""]
    if analysis["cycles"]:
        for number, cycle in enumerate(analysis["cycles"], start=1):
            out.append("### Cycle " + str(number) + " (" + str(len(cycle["members"])) + " documents)")
            out.append("")
            out.append("Members: " + _join(cycle["members"], 12))
            out.append("")
            for src, dst in cycle["edges"][:12]:
                out.append("- " + _code(src) + " depends on " + _code(dst))
            if len(cycle["edges"]) > 12:
                out.append("- (+" + str(len(cycle["edges"]) - 12) + " more links)")
            out.append("")
    else:
        out.append("No cycles found.")

    out += ["", "## Missing documents", ""]
    if analysis["unresolved"]:
        out.append("| Referenced ID | Type | Cited by |")
        out.append("|---|---|---|")
        for item in analysis["unresolved"][:config.TOP_RANKED_ROWS]:
            out.append("| " + _code(item["id"]) + " | " + _cell(item["doc_type"]) + " | " + _join(item["cited_by"], 6) + " |")
    else:
        out.append("None.")

    out += ["", "## Suggested change order", ""]
    out.append("Tier 0 documents depend on no other document in the corpus. Each later tier depends only on earlier tiers. Changing upstream documents first lets dependents be updated against their final version. This order is a heuristic; reverse it if your rollout goes top-down. Documents in a cycle share a tier and are shown together.")
    out.append("")
    out.append("| Tier | Documents |")
    out.append("|---|---|")
    for number, units in enumerate(analysis["tiers"]):
        flat = []
        for unit in units:
            flat.append(unit[0] if len(unit) == 1 else "{" + ", ".join(unit) + "} (cycle)")
        shown = ", ".join(_code(u) if not u.startswith("{") else u for u in flat[:25])
        if len(flat) > 25:
            shown += " (+" + str(len(flat) - 25) + " more)"
        out.append("| " + str(number) + " | " + shown + " |")

    out += ["", "## Systems", ""]
    if analysis["systems"]:
        out.append("| System | Documents depending on it | Which |")
        out.append("|---|---|---|")
        for item in analysis["systems"]:
            out.append("| " + _cell(item["id"]) + " | " + str(len(item["dependents"])) + " | " + _join(item["dependents"], 6) + " |")
    else:
        out.append("No systems referenced.")

    out += ["", "## Orphans", ""]
    out.append("Documents that neither cite nor are cited by another document: " + _join(analysis["orphans"], 30) + ".")

    out += ["", "## Coverage and limits", ""]
    out.append("| Measure | Value |")
    out.append("|---|---|")
    rows = [
        ("Pages read", stats["pages"]),
        ("Pages with a document ID", stats["pages_with_id"]),
        ("ID sources", ", ".join(k + ": " + str(v) for k, v in sorted(stats["id_sources"].items())) or "-"),
        ("Pages citing no other document", stats["pages_without_doc_refs"]),
        ("Pages that may be cut at the wiki length limit", stats["truncated_pages"]),
        ("References repaired from a malformed ID", stats["normalised_refs"]),
        ("References in change logs (ignored)", stats["change_log_references"]),
        ("Lineage references such as supersedes (ignored)", stats["lineage_references"]),
        ("Self-references (ignored)", stats["self_references"]),
        ("Strings skipped as non-documents (for example ISO-9001)", stats["stoplisted_ids"]),
    ]
    for label, value in rows:
        out.append("| " + label + " | " + _cell(value) + " |")
    out.append("")
    out.append("- Only references written as document IDs are found. A reference such as \"see the closure SOP\" with no ID is not detected.")
    out.append("- Which strings count as IDs is set in `scripts/dep_utils/config.py`. Edit it to fit the client.")
    if stats["truncated_pages"]:
        out.append("- Pages near the wiki length limit may have lost references past the cut. Treat their dependents as a lower bound.")
    if stats["duplicate_ids"]:
        out.append("- Duplicate document IDs were merged: " + _join(sorted(set(stats["duplicate_ids"])), 10) + ".")

    if graph["warnings"]:
        out += ["", "## Warnings", ""]
        for message in sorted(set(graph["warnings"]))[:20]:
            out.append("- " + message)
        if len(set(graph["warnings"])) > 20:
            out.append("- (+" + str(len(set(graph["warnings"])) - 20) + " more)")
    if stats["normalisations"]:
        out += ["", "## Repaired IDs", ""]
        for raw, target, page in sorted(set(stats["normalisations"]), key=lambda t: tuple(str(x) for x in t))[:15]:
            out.append("- `" + str(raw) + "` read as " + _code(target) + " in " + _code(page))

    evidence = _evidence_rows(graph)
    out += ["", "## Relationship evidence", ""]
    out.append("Each row is source evidence retained for a graph edge. `From → to` is the asserted dependency direction; `Source page`, line, section, and context identify where the reference was found. `Page mentions` is the number of matching references on that source page; `edge total` is the total across all retained source evidence for the edge. `normalised` means the written ID was repaired using the configured ID rules. Review this evidence before treating a relationship as semantically authoritative.")
    out.append("")
    if evidence:
        out.append("| From → to | Source page | Line | Section | Page mentions | Edge total | Confidence | Captured context |")
        out.append("|---|---|---:|---|---:|---:|---|---|")
        for item in evidence[:config.EVIDENCE_MAX_ROWS]:
            direction = _code(item["from"]) + " → " + _code(item["to"])
            out.append("| " + " | ".join([
                direction, _code(item["page"] or "-"), str(item["line"] or "-"),
                _cell(item["section"] or "-"), str(item["page_mentions"]), str(item["edge_mentions"]), _cell(item["confidence"]),
                _cell(item["context"] or "-")]) + " |")
        if len(evidence) > config.EVIDENCE_MAX_ROWS:
            out.append("")
            out.append("Showing the first " + str(config.EVIDENCE_MAX_ROWS) + " of " + str(len(evidence)) +
                       " captured evidence rows, ordered by edge. The complete graph topology is in Graph data; rerun a smaller corpus or increase `EVIDENCE_MAX_ROWS` to review more contextual evidence.")
    else:
        out.append("No retained relationships; there is no relationship evidence to display.")

    selected, edges = diagram_nodes(graph, analysis)
    out += ["", "## Dependency diagram", ""]
    out.append("Top " + str(config.MERMAID_TOP_DOCS) + " documents by blast radius with a few neighbouring systems and missing documents. Red marks cycle members, dashed marks missing documents, hexagons are systems.")
    out += ["", "```mermaid", mermaid_text(graph, analysis, selected, edges), "```"]

    total = len(graph["nodes"]) + len(graph["edges"])
    out += ["", "## Graph data", ""]
    if total <= config.EMBED_JSON_MAX_ITEMS:
        data = graph_json(graph, analysis)
        out.append("Complete graph. Edges point from a document to the document it depends on.")
    else:
        data = graph_json(graph, analysis, selected)
        out.append("The full graph has " + str(total) + " items, too many to embed. This is the diagram subset only.")
    out += ["", "```json", json.dumps(data, separators=(",", ":"), sort_keys=True), "```", ""]
    return "\n".join(out)
