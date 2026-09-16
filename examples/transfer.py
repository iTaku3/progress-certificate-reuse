"""Tiny explanatory transfer model; not a reconstruction of the RBS incident.

The accepted-request monitor belongs to the specification and is NOT reset
when the implementation loses its queue entry. The same new implementation
has both a waiting state and an idle state; only its migration entry differs.
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
    # queue: software still holds an unexecuted request.
    # owed: an accepted external request has not actually been executed.
    # updated: code switch is complete. It alone is not the desired goal.
    states = {
        "old_accepted": {"queue": 1, "owed": 1, "updated": 0},
        "new_waiting": {"queue": 1, "owed": 1, "updated": 1},
        "new_idle_lost": {"queue": 0, "owed": 1, "updated": 1},
        "executed": {"queue": 0, "owed": 0, "updated": 1},
    }
    # GF J means that an outstanding submitted action is not postponed forever.
    # With no queued action J is true. Thus the lost case cannot be hidden by
    # making the environmental assumption false.
    colors = {v: int(not x["queue"]) for v, x in states.items()}
    result = {"states": states, "justice_labels": colors, "cases": {}}
    for migration, entry in [("keep_request", "new_waiting"),
                              ("lose_queue_entry", "new_idle_lost")]:
        graph = {"old_accepted": {entry},
                 "new_waiting": {"new_waiting", "executed"},
                 "new_idle_lost": {"new_idle_lost"},
                 "executed": {"executed"}}
        actual_goal = {v for v, x in states.items() if not x["owed"] and x["updated"]}
        switch_only_goal = {v for v, x in states.items() if x["updated"]}
        actual = base.full_oracle(graph, colors, actual_goal, set(), "old_accepted", 1)
        switch_only = base.full_oracle(graph, colors, switch_only_goal, set(), "old_accepted", 1)
        result["cases"][migration] = {"graph": {v: sorted(ws) for v, ws in graph.items()},
                                     "request_completion": actual,
                                     "switch_completion_only": switch_only}
    expected = {"keep_request": (True, True, True),
                "lose_queue_entry": (True, False, True)}
    for name, values in expected.items():
        got = result["cases"][name]["request_completion"]
        assert tuple(got[k] for k in ["safe", "fair_completion", "nonconflicting"]) == values, got
        assert result["cases"][name]["switch_completion_only"]["fair_completion"]
    result["scope"] = "Four-state explanatory fixed-policy graph with one justice condition. No incident reconstruction, financial implementation, policy synthesis, or timing guarantee."
    result["script_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (RESULTS / "transfer_example_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
