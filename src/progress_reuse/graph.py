"""Finite fixed-policy boundary summaries for progress-preserving reuse.

This is a feasibility prototype, not a controller-synthesis algorithm and not a
claim of a new abstraction theorem. A full-graph oracle uses reachability
equivalence; the summary implementation uses Tarjan SCCs and colored macroedges.
Justice assumptions are conjunctions of GF J_i. Completion is F goal, with goal
absorbing. Deadlocked executions have no fair infinite extension.

The summary retains (1) colors on paths between ports, (2) reachable internal
fair cycles, and (3) families of reachable exit sets for internal states. Item 3
is necessary to check existence of a fair continuation from *every* reachable
prefix, including branches which never return to a port.
"""
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
import datetime
import hashlib
import itertools
import json
import random



def reach(graph, starts):
    seen = set(starts) & graph.keys()
    todo = deque(seen)
    while todo:
        for t in graph[todo.popleft()]:
            if t not in seen:
                seen.add(t)
                todo.append(t)
    return seen


def tarjan(graph):
    index, low, active = {}, {}, set()
    stack, result = [], []

    def visit(s):
        index[s] = low[s] = len(index)
        stack.append(s)
        active.add(s)
        for t in graph[s]:
            if t not in index:
                visit(t)
                low[s] = min(low[s], low[t])
            elif t in active:
                low[s] = min(low[s], index[t])
        if low[s] == index[s]:
            c = set()
            while True:
                t = stack.pop()
                active.remove(t)
                c.add(t)
                if t == s:
                    break
            result.append(c)

    for s in graph:
        if s not in index:
            visit(s)
    return result


def full_oracle(graph, colors, goal, unsafe, start, all_bits):
    """Independent full-state checker, with no interface or cached summary."""
    reached = reach(graph, [start])
    closure = {s: reach(graph, [s]) for s in graph}
    remaining, fair = set(graph), set()
    while remaining:
        s = min(remaining)
        c = {t for t in closure[s] if s in closure[t]}
        remaining -= c
        mask = 0
        for t in c:
            mask |= colors[t]
        if (len(c) > 1 or s in graph[s]) and mask == all_bits:
            fair |= c
    fair_good = {s for s in graph if closure[s] & fair}
    nong = {s: {t for t in ts if t not in goal}
            for s, ts in graph.items() if s not in goal}
    remaining, fair_bad = set(nong), set()
    nclosure = {s: reach(nong, [s]) for s in nong}
    while remaining:
        s = min(remaining)
        c = {t for t in nclosure[s] if s in nclosure[t]}
        remaining -= c
        mask = 0
        for t in c:
            mask |= colors[t]
        if (len(c) > 1 or s in nong[s]) and mask == all_bits:
            fair_bad |= c
    return {
        'safe': not bool(reached & unsafe),
        'fair_completion': not bool(reach(nong, [start]) & fair_bad),
        'nonconflicting': reached <= fair_good,
    }


@dataclass
class Fragment:
    name: str
    graph: dict
    ports: set
    colors: dict
    unsafe: set
    goal: set


def local_summary(fragment, all_bits, avoid_goal=False):
    allowed = set(fragment.graph) - (fragment.goal if avoid_goal else set())
    graph = {s: set(ts) & allowed for s, ts in fragment.graph.items() if s in allowed}
    ports = fragment.ports & allowed
    inside = allowed - ports
    inner = {s: graph[s] & inside for s in inside}
    fair_inner = set()
    for c in tarjan(inner):
        mask = 0
        for s in c:
            mask |= fragment.colors[s]
        if (len(c) > 1 or any(s in inner[s] for s in c)) and mask == all_bits:
            fair_inner |= c
    can_stay_fair = {s for s in inside if reach(inner, [s]) & fair_inner}
    exits = {s: graph[s] & ports for s in inside}
    while True:
        new = {s: exits[s] | set().union(*(exits[t] for t in inner[s]))
               for s in inside}
        if new == exits:
            break
        exits = new

    edges, internal_fair, signatures, bad = set(), set(), {}, set()
    product_visits = 0
    for entry in ports:
        initial = (entry, fragment.colors[entry])
        seen, todo, visited_internal = {initial}, deque([initial]), set()
        while todo:
            s, mask = todo.popleft()
            product_visits += 1
            for t in graph[s]:
                nmask = mask | fragment.colors[t]
                if t in ports:
                    edges.add((entry, t, nmask))
                else:
                    visited_internal.add(t)
                    state = (t, nmask)
                    if state not in seen:
                        seen.add(state)
                        todo.append(state)
        if visited_internal & can_stay_fair:
            internal_fair.add(entry)
        if visited_internal & fragment.unsafe:
            bad.add(entry)
        family = {frozenset(exits[s]) for s in visited_internal - can_stay_fair}
        # Larger exit sets impose no extra requirement if a smaller one exists.
        signatures[entry] = [sorted(x) for x in family
                             if not any(y < x for y in family)]
    return {
        'ports': sorted(ports), 'edges': sorted(edges),
        'internal_fair': sorted(internal_fair),
        'exit_signatures': signatures, 'internal_unsafe': sorted(bad),
        'unsafe_ports': sorted(ports & fragment.unsafe),
        'port_colors': {s: fragment.colors[s] for s in ports},
        'product_visits': product_visits,
    }


def macro_graph(summaries, connectors, all_bits, keep_internal=True):
    colors = {s: m for x in summaries for s, m in x['port_colors'].items()}
    graph = {s: set() for s in colors}
    masks = defaultdict(int)
    for x in summaries:
        for a, b, mask in x['edges']:
            graph[a].add(b)
            masks[a, b] |= mask
        if keep_internal:
            for a in x['internal_fair']:
                # Each sink represents an actually reachable internal fair cycle.
                b = 'fair-stay:' + a
                graph[b] = {b}
                graph[a].add(b)
                masks[a, b] = masks[b, b] = all_bits
    for a, b in connectors:
        if a in colors and b in colors:
            graph[a].add(b)
            masks[a, b] |= colors[a] | colors[b]
    fair = set()
    for c in tarjan(graph):
        mask = 0
        cyclic = len(c) > 1 or any(s in graph[s] for s in c)
        for s in c:
            for t in graph[s] & c:
                mask |= masks[s, t]
        if cyclic and mask == all_bits:
            fair |= c
    good = {s for s in graph if reach(graph, [s]) & fair}
    return graph, good, fair


def summary_check(full, nong, connectors, start, all_bits,
                  keep_signatures=True, keep_bad_internal=True):
    ports = {s for x in full for s in x['ports']}
    if start not in ports or any(a not in ports or b not in ports for a, b in connectors):
        raise ValueError('A new boundary entry requires local summary reconstruction')
    graph, good, _ = macro_graph(full, connectors, all_bits)
    reached = reach(graph, [start])
    badgraph, _, fair_bad = macro_graph(nong, connectors, all_bits,
                                        keep_internal=keep_bad_internal)
    safe = all(not (reached & (set(x['internal_unsafe']) | set(x['unsafe_ports'])))
               for x in full)
    nonconflicting = reached <= good
    if keep_signatures:
        nonconflicting = nonconflicting and all(
            set(exits) & good
            for x in full for entry, family in x['exit_signatures'].items()
            if entry in reached for exits in family)
    return {
        'safe': safe,
        'fair_completion': not bool(reach(badgraph, [start]) & fair_bad),
        'nonconflicting': bool(nonconflicting),
    }


def full_graph(fragments, connectors):
    graph = {s: set(ts) for f in fragments for s, ts in f.graph.items()}
    for s, t in connectors:
        graph[s].add(t)
    colors = {s: m for f in fragments for s, m in f.colors.items()}
    goal = set().union(*(f.goal for f in fragments))
    unsafe = set().union(*(f.unsafe for f in fragments))
    return graph, colors, goal, unsafe

