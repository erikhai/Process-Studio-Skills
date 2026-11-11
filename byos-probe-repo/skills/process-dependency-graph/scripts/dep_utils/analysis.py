"""Graph analysis: cycles, blast radius, change-order tiers, orphans, hubs."""


def strongly_connected(node_ids, adjacency):
    """Iterative Tarjan. Returns components, dependencies first (sinks before sources)."""
    index, low, on_stack, stack, result = {}, {}, set(), [], []
    counter = 0
    for root in node_ids:
        if root in index:
            continue
        index[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on_stack.add(root)
        work = [(root, iter(adjacency.get(root, ())))]
        while work:
            node, neighbours = work[-1]
            advanced = False
            for nxt in neighbours:
                if nxt not in index:
                    index[nxt] = low[nxt] = counter
                    counter += 1
                    stack.append(nxt)
                    on_stack.add(nxt)
                    work.append((nxt, iter(adjacency.get(nxt, ()))))
                    advanced = True
                    break
                if nxt in on_stack:
                    low[node] = min(low[node], index[nxt])
            if advanced:
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
            if low[node] == index[node]:
                component = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    component.append(member)
                    if member == node:
                        break
                result.append(sorted(component))
    return result


def _popcount(value):
    return bin(value).count("1")


def _adjacency(node_ids, edge_pairs):
    out_adj = {n: set() for n in node_ids}
    in_adj = {n: set() for n in node_ids}
    for src, dst in edge_pairs:
        if src in out_adj and dst in out_adj and src != dst:
            out_adj[src].add(dst)
            in_adj[dst].add(src)
    return ({n: sorted(v) for n, v in out_adj.items()}, {n: sorted(v) for n, v in in_adj.items()})


def analyse(graph):
    nodes, edges = graph["nodes"], graph["edges"]
    node_ids = sorted(nodes)
    out_adj, in_adj = _adjacency(node_ids, edges.keys())

    components = strongly_connected(node_ids, out_adj)
    comp_of = {}
    for number, members in enumerate(components):
        for member in members:
            comp_of[member] = number

    position = {node_id: bit for bit, node_id in enumerate(node_ids)}
    members_mask = []
    for members in components:
        mask = 0
        for member in members:
            mask |= 1 << position[member]
        members_mask.append(mask)

    comp_dependents = [set() for _ in components]
    for src, dst in edges:
        if src != dst and comp_of[src] != comp_of[dst]:
            comp_dependents[comp_of[dst]].add(comp_of[src])

    reach = [0] * len(components)
    for number in range(len(components) - 1, -1, -1):
        mask = 0
        for dependent in comp_dependents[number]:
            mask |= members_mask[dependent] | reach[dependent]
        reach[number] = mask

    cycles = []
    cycle_of = {}
    for number, members in enumerate(components):
        if len(members) > 1:
            member_set = set(members)
            cycle_edges = sorted((s, d) for (s, d) in edges if s in member_set and d in member_set)
            cycles.append({"members": members, "edges": cycle_edges})
    cycles.sort(key=lambda c: (-len(c["members"]), c["members"][0]))
    for cycle_number, cycle in enumerate(cycles, start=1):
        for member in cycle["members"]:
            cycle_of[member] = cycle_number

    metrics = {}
    for node_id in node_ids:
        number = comp_of[node_id]
        metrics[node_id] = {
            "dependents": len(in_adj[node_id]),
            "dependencies": len(out_adj[node_id]),
            "blast": _popcount(reach[number]) + len(components[number]) - 1,
            "cycle": cycle_of.get(node_id),
            "tier": None,
        }

    tiers = _tiers(nodes, edges)
    for tier_number, units in enumerate(tiers):
        for unit in units:
            for member in unit:
                metrics[member]["tier"] = tier_number

    documents = [n for n in node_ids if nodes[n]["kind"] == "document"]
    ranking = sorted(documents, key=lambda n: (-metrics[n]["blast"], -metrics[n]["dependents"], n))

    unresolved = []
    for node_id in node_ids:
        if nodes[node_id]["kind"] == "unresolved":
            unresolved.append({"id": node_id, "doc_type": nodes[node_id]["doc_type"],
                               "cited_by": sorted(set(in_adj[node_id]) | set(out_adj[node_id]))})
    unresolved.sort(key=lambda u: (-len(u["cited_by"]), u["id"]))

    systems = [{"id": n, "dependents": in_adj[n], "blast": metrics[n]["blast"]}
               for n in node_ids if nodes[n]["kind"] == "system"]
    systems.sort(key=lambda s: (-len(s["dependents"]), s["id"]))

    orphans = []
    for node_id in documents:
        linked = [m for m in in_adj[node_id] + out_adj[node_id] if nodes[m]["kind"] != "system"]
        if not linked:
            orphans.append(node_id)

    return {
        "in_adj": in_adj, "out_adj": out_adj, "metrics": metrics, "cycles": cycles,
        "ranking": ranking, "unresolved": unresolved, "systems": systems,
        "orphans": orphans, "tiers": tiers,
    }


def _tiers(nodes, edges):
    """Layer the resolved documents. Tier 0 depends on no other document; cycles form one unit."""
    docs = sorted(n for n in nodes if nodes[n]["kind"] == "document")
    doc_set = set(docs)
    doc_edges = [(s, d) for (s, d) in edges if s in doc_set and d in doc_set]
    out_adj, _ = _adjacency(docs, doc_edges)
    components = strongly_connected(docs, out_adj)
    comp_of = {m: i for i, members in enumerate(components) for m in members}
    tier_of = [0] * len(components)
    for number, members in enumerate(components):
        best = -1
        for member in members:
            for dep in out_adj[member]:
                other = comp_of[dep]
                if other != number:
                    best = max(best, tier_of[other])
        tier_of[number] = best + 1
    layers = {}
    for number, members in enumerate(components):
        layers.setdefault(tier_of[number], []).append(members)
    return [sorted(layers[t], key=lambda unit: unit[0]) for t in sorted(layers)]
