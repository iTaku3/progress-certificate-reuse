"""Original adapter helpers; use the public package's record implementations."""
from pathlib import Path
import json
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from progress_reuse import graph as base
from progress_reuse.composition import compose

CONTROLLABLE = {"initInventory", "initCredit", "eval", "initShipping",
                "initBilling", "archive", "rollback"}


def read_aut(path):
    rows = path.read_text().splitlines()
    start, transitions, size = map(int, re.fullmatch(r"des\((\d+),(\d+),(\d+)\)", rows[0]).groups())
    edges = {i: [] for i in range(size)}
    for row in rows[1:]:
        s, event, t = re.fullmatch(r"\((\d+),([^,]+),(\d+)\)", row).groups()
        edges[int(s)].append((event, int(t)))
    assert sum(map(len, edges.values())) == transitions
    return start, edges


def canonical(record):
    record = {k: v for k, v in record.items() if k != "product_visits"}
    record["exit_signatures"] = {k: sorted(v) for k, v in record["exit_signatures"].items()}
    return json.dumps(record, ensure_ascii=False, sort_keys=True)


def merge(fragments, connectors, external):
    graph, colors, goal, unsafe = base.full_graph(fragments, connectors)
    return base.Fragment("merged", graph, set(external), colors, unsafe, goal)
