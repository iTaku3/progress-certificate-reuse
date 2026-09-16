"""Reproducible validation against directly rebuilt and full-state results.

The full-state checker does not consult records. Direct records are constructed
from actual hidden states. Failures are saved and stop this run. Success is
finite testing, not a proof. No strategy search, performance comparison with
published synthesis engines, or unexpanded parallel composition is claimed.
"""
import argparse
from collections import Counter
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import sys
import time


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / 'src'))
from progress_reuse import graph as base
RESULTS = ROOT / 'results'
RESULTS.mkdir(exist_ok=True)
SOURCE = ROOT / 'src/progress_reuse/graph.py'
from progress_reuse.composition import compose


def canonical(record):
    record = {k: v for k, v in record.items() if k != 'product_visits'}
    record['exit_signatures'] = {k: sorted(v) for k, v in record['exit_signatures'].items()}
    return json.dumps(record, ensure_ascii=False, sort_keys=True)


def merge(fragments, connectors, external):
    graph, colors, goal, unsafe = base.full_graph(fragments, connectors)
    return base.Fragment('merged', graph, set(external), colors, unsafe, goal)


def random_case(rng, index):
    justice = index % 4
    all_bits = (1 << justice) - 1
    fragments = []
    for part in range(3):
        size = rng.randint(3, 10)
        vertices = [f'{part}:{i}' for i in range(size)]
        ports = set(rng.sample(vertices, rng.randint(1, min(4, size))))
        goal = {v for v in vertices if rng.random() < .10}
        density = rng.choice([.06, .15, .30, .55])
        graph = {v: ({v} if v in goal else {t for t in vertices if rng.random() < density})
                 for v in vertices}
        colors = {v: rng.randrange(all_bits + 1) for v in vertices}
        unsafe = {v for v in vertices if rng.random() < .09}
        fragments.append(base.Fragment(str(part), graph, ports, colors, unsafe, goal))
    ports = sorted(set().union(*(f.ports for f in fragments)))
    goal = set().union(*(f.goal for f in fragments))
    # Cross-part movement is possible solely at declared ports. Goal is absorbing.
    density = rng.choice([.05, .15, .35, .65])
    connectors = [(s, t) for s in ports for t in ports
                  if s[0] != t[0] and s not in goal and rng.random() < density]
    external = set(rng.sample(ports, rng.randint(1, len(ports))))
    return fragments, connectors, external, all_bits


def serializable_case(fragments, connectors, external, all_bits):
    return {
        'all_bits': all_bits, 'connectors': connectors, 'external_ports': sorted(external),
        'fragments': [{
            'name': f.name, 'graph': {s: sorted(ts) for s, ts in f.graph.items()},
            'colors': f.colors, 'ports': sorted(f.ports),
            'unsafe': sorted(f.unsafe), 'goal': sorted(f.goal),
        } for f in fragments],
    }


def validate(fragments, connectors, external, all_bits, counts):
    joined = merge(fragments, connectors, external)
    records = {}
    for avoid_goal in [False, True]:
        local = [base.local_summary(f, all_bits, avoid_goal) for f in fragments]
        available = set().union(*(set(r['ports']) for r in local))
        con = [(s, t) for s, t in connectors if s in available and t in available]
        exposed = external & available
        flat = compose(local, con, exposed, all_bits)
        direct = base.local_summary(joined, all_bits, avoid_goal)
        assert canonical(flat) == canonical(direct), {
            'kind': 'flat-v-direct', 'avoid_goal': avoid_goal,
            'flat': flat, 'direct': direct,
        }
        counts['record_equality_checks'] += 1

        # Compose A+B first, retaining only final ports and the endpoints needed
        # to connect C. Then hide intermediate ports and compare final records.
        ab = set(local[0]['ports']) | set(local[1]['ports'])
        c_ports = set(local[2]['ports'])
        ab_con = [(s, t) for s, t in con if s in ab and t in ab]
        outer_con = [(s, t) for s, t in con if s in c_ports or t in c_ports]
        ab_external = (exposed & ab) | ({v for pair in outer_con for v in pair} & ab)
        intermediate = compose(local[:2], ab_con, ab_external, all_bits)
        nested = compose([intermediate, local[2]], outer_con, exposed, all_bits)
        assert canonical(nested) == canonical(direct), {
            'kind': 'nested-v-direct', 'avoid_goal': avoid_goal,
            'nested': nested, 'direct': direct,
        }
        counts['record_equality_checks'] += 1
        counts['hidden_ports'] += len(available - exposed)
        counts['empty_signatures'] += sum([] in family for family in flat['exit_signatures'].values())
        records[avoid_goal] = flat

    for start in sorted(external):
        direct = base.full_oracle(joined.graph, joined.colors, joined.goal, joined.unsafe, start, all_bits)
        summarized = base.summary_check([records[False]], [records[True]], [], start, all_bits)
        assert summarized == direct, {'kind': 'three-guarantees', 'start': start,
                                      'summary': summarized, 'direct': direct}
        counts['start_state_checks'] += 1
        counts['individual_guarantee_checks'] += 3
        counts['truth_pattern_' + ''.join(str(int(direct[x])) for x in ['safe', 'fair_completion', 'nonconflicting'])] += 1
    return records


def negative_controls(counts):
    # A fair branch must not hide a second branch trapped in an unfair self-loop.
    a = base.Fragment('A', {'a': {'h', 'b'}, 'h': {'h'}, 'b': {'b'}}, {'a', 'b'},
                      {'a': 0, 'h': 0, 'b': 1}, set(), {'b'})
    full = base.local_summary(a, 1)
    nong = base.local_summary(a, 1, True)
    exact = base.summary_check([full], [nong], [], 'a', 1)
    damaged = base.summary_check([full], [nong], [], 'a', 1, keep_signatures=False)
    assert exact['nonconflicting'] is False and damaged['nonconflicting'] is True
    counts['negative_control_trap_detected'] += 1
    for connectors, ports in [([('a', 'h')], {'a'}), ([], {'h'})]:
        try:
            compose([full], connectors, ports, 1)
        except ValueError:
            counts['negative_control_new_entry_rejected'] += 1
        else:
            raise AssertionError('An unrecorded entry must be rejected')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cases', type=int, default=5000)
    parser.add_argument('--seed', type=int, default=20260910)
    parser.add_argument('--output', default='record_composition_results.json')
    args = parser.parse_args()
    began = time.perf_counter()
    rng, counts = random.Random(args.seed), Counter()
    for index in range(args.cases):
        inputs = random_case(rng, index)
        try:
            validate(*inputs, counts)
        except Exception as error:
            failure = serializable_case(*inputs)
            failure.update({'index': index, 'seed': args.seed, 'error': repr(error)})
            path = RESULTS / f'failure_seed{args.seed}_case{index}.json'
            path.write_text(json.dumps(failure, ensure_ascii=False, indent=2))
            raise
        counts['cases'] += 1
        counts[f'justice_conditions_{index % 4}'] += 1
    negative_controls(counts)
    result = {
        'time': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'python': sys.version, 'seed': args.seed, 'counts': dict(counts),
        'elapsed_seconds': time.perf_counter() - began,
        'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in [SOURCE, ROOT / 'src/progress_reuse/composition.py', Path(__file__)]},
        'limits': [
            'Finite fixed-policy graphs; memory and simultaneous behavior already expanded.',
            'Cross-fragment edges are permitted only at typed recorded ports.',
            'Conjunctions of 0-3 GF justice conditions; absorbing completion states.',
            'No candidate-strategy search, assumption-changing migration, or measured synthesis advantage.',
            'Random tests and direct-record checks are supporting evidence, not a general proof.',
        ],
    }
    (RESULTS / args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
