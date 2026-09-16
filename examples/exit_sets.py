"""Three-state explanation of why an empty exit set must not be omitted.

Fixed-policy finite graph; one GF justice assumption; no transfer or synthesis.
The negative control deliberately omits the internal exit-set obligations.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / 'src'))
from progress_reuse import graph as base
RESULTS = ROOT / 'results'
RESULTS.mkdir(exist_ok=True)
SOURCE = ROOT / 'src/progress_reuse/graph.py'


def main():
    graph = {'accepted': {'completed', 'trapped'},
             'completed': {'completed'}, 'trapped': {'trapped'}}
    colors = {'accepted': 0, 'completed': 1, 'trapped': 0}
    fragment = base.Fragment('example', graph, {'accepted', 'completed'},
                             colors, set(), {'completed'})
    normal = base.local_summary(fragment, 1, False)
    avoid = base.local_summary(fragment, 1, True)
    full = base.full_oracle(graph, colors, {'completed'}, set(), 'accepted', 1)
    recorded = base.summary_check([normal], [avoid], [], 'accepted', 1)
    omitted = base.summary_check([normal], [avoid], [], 'accepted', 1,
                                  keep_signatures=False)
    expected = {'safe': True, 'fair_completion': True, 'nonconflicting': False}
    assert full == recorded == expected
    assert omitted == {**expected, 'nonconflicting': True}
    assert normal['exit_signatures']['accepted'] == [[]]
    result = {'scope': __doc__, 'graph': {k: sorted(v) for k,v in graph.items()},
              'colors': colors, 'ports': ['accepted', 'completed'],
              'full_graph': full, 'with_exit_sets': recorded,
              'without_exit_sets_negative_control': omitted,
              'accepted_exit_sets': normal['exit_signatures']['accepted'],
              'sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in [SOURCE, Path(__file__)]}}
    (RESULTS / 'exit_set_counterexample.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
