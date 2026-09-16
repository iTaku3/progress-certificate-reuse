"""Compose fixed-policy GF-justice boundary records without internal graphs.

The input is the record format of progress_reuse/graph.py. This is a
feasibility implementation for a restricted finite-state model, not a synthesis
engine or a proof of novelty. All vertices and strategy memories must already
be included in the records' port types. Connectors may join existing ports only.
The operator supports hiding old ports, including in cyclic compositions.
"""
from collections import defaultdict, deque


def reachable(graph, starts):
    seen = set(starts) & graph.keys()
    todo = deque(seen)
    while todo:
        for target in graph[todo.popleft()]:
            if target not in seen:
                seen.add(target)
                todo.append(target)
    return seen


def components(graph):
    """Iterative Kosaraju: independent of the direct-record Tarjan routine."""
    seen, order = set(), []
    for root in graph:
        if root in seen:
            continue
        seen.add(root)
        stack = [(root, iter(graph[root]))]
        while stack:
            vertex, following = stack[-1]
            try:
                target = next(following)
            except StopIteration:
                order.append(vertex)
                stack.pop()
                continue
            if target not in seen:
                seen.add(target)
                stack.append((target, iter(graph[target])))
    reverse = {s: set() for s in graph}
    for s in graph:
        for t in graph[s]:
            reverse[t].add(s)
    seen = set()
    for root in reversed(order):
        if root not in seen:
            group = reachable(reverse, [root]) - seen
            seen |= group
            yield group


def minimize(family):
    family = set(family)
    return sorted([sorted(x) for x in family if not any(y < x for y in family)])


def compose(records, connectors, external_ports, all_bits):
    """Return a record using only records, connector pairs and external ports.

    No graph, component implementation, or hidden vertex identifier is accepted.
    Filtering deleted goal ports for a goal-avoiding record is the caller's job.
    """
    ports = set()
    colors, signatures = {}, {}
    local_fair, local_unsafe, unsafe_ports = set(), set(), set()
    edge_sets = defaultdict(set)
    for record in records:
        current = set(record['ports'])
        if ports & current:
            raise ValueError('Record ports must be disjoint')
        ports |= current
        colors.update(record['port_colors'])
        signatures.update(record['exit_signatures'])
        local_fair.update(record['internal_fair'])
        local_unsafe.update(record['internal_unsafe'])
        unsafe_ports.update(record['unsafe_ports'])
        for s, t, mask in record['edges']:
            edge_sets[s].add((t, mask))
    external = set(external_ports)
    if not external <= ports:
        raise ValueError('A new external entry requires record reconstruction')
    if any(s not in ports or t not in ports for s, t in connectors):
        raise ValueError('A new connector entry requires record reconstruction')
    for s, t in connectors:
        edge_sets[s].add((t, colors[s] | colors[t]))
    hidden = ports - external
    inner = {s: {t for t, mask in edge_sets[s] if t in hidden} for s in hidden}

    # A fair path staying inside either remains in an old component forever or
    # visits old (now hidden) ports infinitely often.
    fair = local_fair & hidden
    for group in components(inner):
        mask = 0
        for s in group:
            for t, edge_mask in edge_sets[s]:
                if t in group:
                    mask |= edge_mask
        cyclic = len(group) > 1 or any(s in inner[s] for s in group)
        if cyclic and mask == all_bits:
            fair |= group
    good = {s for s in hidden if reachable(inner, [s]) & fair}

    # E(s) gives external exits reachable without another external port en route.
    exit_sets = {}
    for s in hidden:
        reached = reachable(inner, [s])
        exit_sets[s] = frozenset(t for p in reached for t, _ in edge_sets[p]
                                 if t in external)

    edges, internal_fair, internal_unsafe, new_signatures = set(), set(), set(), {}
    product_visits = 0
    for entry in external:
        seen, todo = {(entry, colors[entry])}, deque([(entry, colors[entry])])
        visited = {entry}
        while todo:
            s, mask = todo.popleft()
            product_visits += 1
            for t, edge_mask in edge_sets[s]:
                next_mask = mask | edge_mask
                if t in external:
                    edges.add((entry, t, next_mask))
                else:
                    visited.add(t)
                    state = (t, next_mask)
                    if state not in seen:
                        seen.add(state)
                        todo.append(state)
        if entry in local_fair or visited & good:
            internal_fair.add(entry)
        if visited & local_unsafe or (visited - {entry}) & unsafe_ports:
            internal_unsafe.add(entry)

        obligations = {exit_sets[s] for s in (visited & hidden) - good}
        for p in visited:
            for exits in signatures[p]:
                exits = set(exits)
                if exits & good:
                    continue
                mapped = set(exits) & external
                for s in exits & hidden:
                    mapped.update(exit_sets[s])
                obligations.add(frozenset(mapped))
        new_signatures[entry] = minimize(obligations)
    return {
        'ports': sorted(external), 'edges': sorted(edges),
        'internal_fair': sorted(internal_fair),
        'exit_signatures': new_signatures,
        'internal_unsafe': sorted(internal_unsafe),
        'unsafe_ports': sorted(external & unsafe_ports),
        'port_colors': {s: colors[s] for s in sorted(external)},
        'product_visits': product_visits,
    }
