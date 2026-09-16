"""Check existing MTSA AUT exports against direct graphs and historical results."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path

from measure import measure

HERE = Path(__file__).resolve().parent


def deterministic_result(result):
    """Exclude measured durations, retaining every structural/checking field."""
    result = json.loads(json.dumps(result))
    for field in ("old_initial_record_ms", "samples", "timing_summary"):
        result.pop(field)
    for field in ("old_structure", "new_structure"):
        result[field]["all_cross_edges"].sort()
    return result


def verify(input_root, output_root, jobs):
    input_root, output_root = Path(input_root), Path(output_root)
    output_root.mkdir(parents=True, exist_ok=False)
    report = {
        "kind": "new record-checking run on supplied AUT exports",
        "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "checks": [],
        "scope": "Direct graph checking, full/local record equality and negative control; no claim of repeating MTSA generation.",
    }
    for n in jobs:
        expected = json.loads((HERE / f"historical/n{n}-record-measurement.json").read_text())
        actual = measure(n, input_root, output_root)
        if deterministic_result(actual) != deterministic_result(expected):
            raise AssertionError(f"n={n}: non-timing fields differ from the historical result")
        report["checks"].append({
            "n": n,
            "new_episode_states": actual["new_structure"]["episode_states"],
            "all_non_timing_fields_match": True,
            "input_sha256": {version: hashlib.sha256((input_root / f"n{n}/{version}.aut").read_bytes()).hexdigest()
                             for version in ("old", "new")},
        })
    report["finished_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    (output_root / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Directory with n2/old.aut, n2/new.aut, etc.")
    parser.add_argument("--output", type=Path, required=True, help="New directory; never overwrites a previous run.")
    parser.add_argument("--jobs", type=int, nargs="+", choices=range(2, 7), default=list(range(2, 7)))
    args = parser.parse_args()
    print(json.dumps(verify(args.input, args.output, args.jobs), indent=2))
