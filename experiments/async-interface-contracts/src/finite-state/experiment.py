#!/usr/bin/env python3
"""Small, explicit-state experiment; not a verifier for arbitrary Node-RED flows.

Only Python's standard library is required. Models: one finite execution of each
job, no failures or retries, full observation, unbounded choice of event order.
"""
from __future__ import annotations

import argparse
from collections import deque
from datetime import datetime, timezone
import hashlib
from itertools import combinations, product
import json
from pathlib import Path
import platform
import time

DEADLINE = datetime.fromisoformat("2026-09-08T11:00:00+09:00")


def check_deadline(enforce: bool) -> None:
    if enforce and datetime.now(timezone.utc) >= DEADLINE:
        raise SystemExit("Research deadline reached; no new experiment started.")


def unsafe(state, edges):
    return any(state[i] == state[j] == 2 for i, j in edges)


def env_successors(state):
    for i, phase in enumerate(state):
        if phase in (1, 2):
            new = list(state)
            new[i] += 1
            yield ("start" if phase == 1 else "finish") + f":{i}", tuple(new)


def control_successors(state):
    for i, phase in enumerate(state):
        if phase == 0:
            new = list(state)
            new[i] = 1
            yield f"dispatch:{i}", tuple(new)


def solve_full_game(n, edges):
    """Independent full-product greatest fixed point, including non-deadlock.

    Every enabled uncontrollable action must stay winning. At a nonterminal
    state with no uncontrollable action, at least one control must stay winning.
    Termination of this specific acyclic model follows from increasing phases.
    """
    all_states = tuple(product(range(4), repeat=n))
    winning = {s for s in all_states if not unsafe(s, edges)}
    iterations = 0
    while True:
        iterations += 1
        remove = set()
        for s in winning:
            u = tuple(t for _, t in env_successors(s))
            if any(t not in winning for t in u):
                remove.add(s)
            elif not u and any(x != 3 for x in s):
                if not any(t in winning for _, t in control_successors(s)):
                    remove.add(s)
        if not remove:
            return all_states, winning, iterations
        winning.difference_update(remove)


def allowed_dispatch(state, i, edges, policy, winning):
    if state[i] != 0:
        return False
    if policy == "full_game":
        t = list(state)
        t[i] = 1
        return tuple(t) in winning
    if policy == "global_serial":
        return not any(x in (1, 2) for x in state)
    occupied = {
        "active_only": (2,),
        "release_on_start": (1,),
        "reserve_until_finish": (1, 2),
    }[policy]
    neighbours = [b if a == i else a for a, b in edges if i in (a, b)]
    return not any(state[j] in occupied for j in neighbours)


def reachable(n, edges, policy, winning):
    initial = (0,) * n
    parents = {initial: None}
    queue = deque([initial])
    bad = []
    blocked = []
    max_parallel = 0
    while queue:
        s = queue.popleft()
        max_parallel = max(max_parallel, s.count(2))
        if unsafe(s, edges):
            bad.append(s)
        # Keep exploring after a violation so the denominator is not truncated.
        outgoing = list(env_successors(s))
        outgoing.extend((a, t) for a, t in control_successors(s)
                        if allowed_dispatch(s, int(a.split(":")[1]), edges,
                                            policy, winning))
        if not outgoing and s != (3,) * n:
            blocked.append(s)
        for action, t in outgoing:
            if t not in parents:
                parents[t] = (s, action)
                queue.append(t)
    witness = []
    if bad:
        s = bad[0]
        while parents[s] is not None:
            prev, action = parents[s]
            witness.append({"action": action, "state": list(s)})
            s = prev
        witness.append({"action": "initial", "state": list(s)})
        witness.reverse()
    return {
        "policy": policy, "reachable_states": len(parents),
        "unsafe_states": len(bad), "deadlock_states": len(blocked),
        "max_parallel": max_parallel, "all_done_reachable": (3,) * n in parents,
        "first_counterexample": witness,
    }


def cases():
    for n in range(2, 7):
        families = {
            "path": {(i, i + 1) for i in range(n - 1)},
            "clique": set(combinations(range(n), 2)),
            "star": {(0, i) for i in range(1, n)},
            "cycle": {(i, i + 1) for i in range(n - 1)} | {(0, n - 1)},
            "empty": set(),
        }
        for name, edges in families.items():
            yield f"{name}_{n}", n, sorted(edges)
    possible = tuple(combinations(range(4), 2))
    for bits in range(1 << len(possible)):
        yield f"all_graphs_n4_{bits:02d}", 4, [edge for j, edge in enumerate(possible)
                                             if bits & (1 << j)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--enforce-deadline", action="store_true",
                        help="Stop the authorized 2026-09-08 research at 11:00 JST")
    args = parser.parse_args()
    check_deadline(args.enforce_deadline)
    if args.output.exists():
        raise SystemExit("Output exists; preserve the original experiment record.")
    args.output.mkdir(parents=True)
    inputs = [{"id": name, "n": n, "edges": edges} for name, n, edges in cases()]
    (args.output / "inputs.json").write_text(json.dumps(inputs, indent=2) + "\n")
    rows = []
    for case in inputs:
        check_deadline(args.enforce_deadline)
        n, edges = case["n"], case["edges"]
        begin = time.perf_counter()
        all_states, winning, iterations = solve_full_game(n, edges)
        oracle_s = time.perf_counter() - begin
        # Direct comparison on every winning state, not only one execution.
        disagreements = []
        for s in sorted(winning):
            for i in range(n):
                local = allowed_dispatch(s, i, edges, "reserve_until_finish", winning)
                oracle = allowed_dispatch(s, i, edges, "full_game", winning)
                if local != oracle:
                    disagreements.append({"state": s, "job": i})
        row = dict(case, product_states=len(all_states), winning_states=len(winning),
                   fixed_point_iterations=iterations, oracle_seconds=oracle_s,
                   decision_disagreements=disagreements, policies=[])
        for policy in ("active_only", "release_on_start", "reserve_until_finish",
                       "global_serial", "full_game"):
            row["policies"].append(reachable(n, edges, policy, winning))
        rows.append(row)
        with (args.output / "cases.jsonl").open("a") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    by_policy = {}
    for policy in rows[0]["policies"]:
        name = policy["policy"]
        matching = [p for r in rows for p in r["policies"] if p["policy"] == name]
        by_policy[name] = {
            "cases": len(matching),
            "unsafe_cases": sum(p["unsafe_states"] > 0 for p in matching),
            "deadlock_cases": sum(p["deadlock_states"] > 0 for p in matching),
            "all_done_cases": sum(p["all_done_reachable"] for p in matching),
        }
    improved_parallel = sum(
        next(p["max_parallel"] for p in r["policies"] if p["policy"] == "reserve_until_finish")
        > next(p["max_parallel"] for p in r["policies"] if p["policy"] == "global_serial")
        for r in rows)
    summary = {
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(), "platform": platform.platform(),
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "inputs_sha256": hashlib.sha256((args.output / "inputs.json").read_bytes()).hexdigest(),
        "cases": len(rows), "distinct_labelled_inputs": len({(r["n"], tuple(map(tuple, r["edges"]))) for r in rows}),
        "scope": "synthetic finite job models; not Node-RED or CNT validation",
        "policy_summary": by_policy,
        "cases_parallelism_above_serial": improved_parallel,
        "all_winning_states_admission_disagreements": sum(len(r["decision_disagreements"]) for r in rows),
        "novelty_claim": "none: reservation is a known baseline; this is a preparation experiment",
    }
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
