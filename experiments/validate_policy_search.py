"""Bounded synthesis feasibility: enumerate local choices, compose records.

Three sequential fragments, two binary control choices per fragment, all
environment edges retained. The synthesis path never constructs a combined
state graph; the exhaustive validation path deliberately does so independently.
This is not unexpanded parallel synthesis or a competitive benchmark.
"""
from collections import Counter
from dataclasses import replace
import hashlib
import itertools
import json
from pathlib import Path
import random
import time

from validate_composition import base, canonical, merge, ROOT, RESULTS
from progress_reuse.composition import compose

HERE = Path(__file__).resolve().parent


def pair_key(pair):
    return tuple(canonical(rec) for rec in pair)


def local_candidates(game, controlled, all_bits):
    candidates = []
    for chosen in itertools.product(*(sorted(game.graph[v]) for v in controlled)):
        choices = dict(zip(controlled, chosen))
        graph = {v: ({choices[v]} if v in choices else set(ws))
                 for v, ws in game.graph.items()}
        fragment = replace(game, graph=graph)
        record = tuple(base.local_summary(fragment, all_bits, avoid)
                       for avoid in [False, True])
        candidates.append({"records": record, "choices": choices,
                           "fragment": fragment})
    return candidates


def combine_records(left, right, connections, external, all_bits):
    result = []
    for i in [0, 1]:
        available = set(left[i]["ports"]) | set(right[i]["ports"])
        cons = [(s, t) for s, t in connections if s in available and t in available]
        result.append(compose([left[i], right[i]], cons, external & available, all_bits))
    return tuple(result)


def record_search(libraries, connections, external, all_bits):
    # Only record pairs and opaque indices enter this stage. Local game graphs,
    # vertex labels, and policies remain outside this function.
    ab_ports = set(libraries[0][0][0]["ports"]) | set(libraries[1][0][0]["ports"])
    ab_cons = [(s, t) for s, t in connections if s in ab_ports and t in ab_ports]
    outer_cons = [(s, t) for s, t in connections if s not in ab_ports or t not in ab_ports]
    middle_external = (external & ab_ports) | ({v for edge in outer_cons for v in edge} & ab_ports)
    middle, final = {}, {}
    operations = 0
    for ai, a in enumerate(libraries[0]):
        for bi, b in enumerate(libraries[1]):
            pair = combine_records(a, b, ab_cons, middle_external, all_bits)
            middle.setdefault(pair_key(pair), (pair, (ai, bi)))
            operations += 1
    for pair, indices in middle.values():
        for ci, c in enumerate(libraries[2]):
            final_pair = combine_records(pair, c, outer_cons, external, all_bits)
            final.setdefault(pair_key(final_pair), (final_pair, indices + (ci,)))
            operations += 1
    return final, {"initial_local_candidates": sum(map(len, libraries)),
                   "first_compositions": len(libraries[0]) * len(libraries[1]),
                   "distinct_intermediate_records": len(middle),
                   "record_compositions": operations,
                   "distinct_final_records": len(final)}


def random_game(rng, index):
    all_bits = (1 << (index % 4)) - 1
    games, owners = [], []
    for part in range(3):
        entry, port_exit = f"{part}:in", f"{part}:out"
        controlled = [f"{part}:c0", f"{part}:c1"]
        internal_env = [f"{part}:e0", f"{part}:e1"]
        vertices = [entry, port_exit] + controlled + internal_env
        graph = {entry: set(rng.sample(controlled, rng.randint(1, 2))),
                 port_exit: ({port_exit} if part == 2 else set())}
        for v in controlled:
            graph[v] = set(rng.sample(vertices, 2))
        for v in internal_env:
            graph[v] = {w for w in vertices if rng.random() < .30}
        colors = {v: rng.randrange(all_bits + 1) for v in vertices}
        if part == 2:
            colors[port_exit] = all_bits
        unsafe = {v for v in vertices if rng.random() < .06}
        games.append(base.Fragment(str(part), graph, {entry, port_exit}, colors,
                                   unsafe, {port_exit} if part == 2 else set()))
        owners.append(controlled)
    connections = [("0:out", "1:in"), ("1:out", "2:in")]
    if index % 3 == 0:
        connections.append(("0:out", "2:in"))  # environmental branch remains
    return games, owners, connections, {"0:in", "2:out"}, all_bits


def check_case(rng, index, totals, outcomes):
    games, owners, connections, external, all_bits = random_game(rng, index)
    candidates = [local_candidates(g, c, all_bits) for g, c in zip(games, owners)]
    result, counts = record_search([[c["records"] for c in cs] for cs in candidates],
                                  connections, external, all_bits)
    totals.update(counts)
    exhaustive, realizable = {}, False
    for selected in itertools.product(*candidates):
        parts = [c["fragment"] for c in selected]
        full = merge(parts, connections, external)
        direct = tuple(base.local_summary(full, all_bits, avoid) for avoid in [False, True])
        check = base.full_oracle(full.graph, full.colors, full.goal, full.unsafe,
                                 "0:in", all_bits)
        key = pair_key(direct)
        if key in exhaustive:
            assert exhaustive[key] == check
        exhaustive[key] = check
        realizable |= all(check.values())
        totals["exhaustive_global_policies"] += 1
        outcomes[tuple(check.values())] += 1
    assert result.keys() == exhaustive.keys(), (index, "lost-or-added-record")
    staged_realizable = False
    for key, (records, indices) in result.items():
        macro = base.summary_check([records[0]], [records[1]], [], "0:in", all_bits)
        assert macro == exhaustive[key], (index, "semantic-mismatch", macro, exhaustive[key])
        # Reconstruct only the selected witness for independent validation.
        selected = [candidates[p][i] for p, i in enumerate(indices)]
        for p, c in enumerate(selected):
            for v in games[p].graph:
                if v in owners[p]:
                    assert len(c["fragment"].graph[v]) == 1
                    assert c["fragment"].graph[v] <= games[p].graph[v]
                else:
                    assert c["fragment"].graph[v] == games[p].graph[v]
        full = merge([c["fragment"] for c in selected], connections, external)
        witness = base.full_oracle(full.graph, full.colors, full.goal, full.unsafe,
                                   "0:in", all_bits)
        assert witness == macro
        totals["independently_checked_representatives"] += 1
        staged_realizable |= all(macro.values())
    assert staged_realizable == realizable
    totals["realizable_instances"] += realizable
    totals["unrealizable_within_memoryless_class"] += not realizable
    if counts["distinct_intermediate_records"] < 16:
        totals["instances_with_intermediate_merging"] += 1


def main():
    count, seed = 120, 2026091027
    rng, totals, outcomes = random.Random(seed), Counter(), Counter()
    started = time.monotonic()
    for i in range(count):
        try:
            check_case(rng, i, totals, outcomes)
        except Exception:
            (RESULTS / "record_policy_search_failure.json").write_text(json.dumps({
                "seed": seed, "failed_index": i, "totals_before_failure": dict(totals)}, indent=2))
            raise
    result = {"cases": count, "seed": seed, "states_per_instance": 18,
              "choices": "Six binary memoryless controlled choices, all environment choices retained",
              "justice_conditions": [0, 1, 2, 3], "totals": dict(totals),
              "truth_patterns_safe_completion_nonconflict": {str(k): v for k, v in outcomes.items()},
              "elapsed_seconds": time.monotonic() - started,
              "claims": "All final record classes, bounded realizability, and representative strategies matched full enumeration in 120 instances. This is finite validation, not proof or a performance comparison.",
              "excluded": "General shared-memory policies, unexpanded parallel products, arbitrary migration changes, competitive performance.",
              "sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__), ROOT / 'src/progress_reuse/composition.py']}}
    (RESULTS / "record_policy_search_results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
