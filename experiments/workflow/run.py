"""Fetch, transform, compile and check the Workflow experiments with a supplied MTSA jar."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

from fetch_model import fetch
from generate import source
from verify_exports import verify

HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jar", type=Path, required=True, help="User-supplied compatible MTSA jar (not distributed).")
    parser.add_argument("--output", type=Path, required=True, help="A new output directory.")
    parser.add_argument("--jobs", type=int, nargs="+", choices=range(2, 8), default=[2])
    parser.add_argument("--heap", default="2g", help="JVM maximum heap, e.g. 2g or 8g.")
    parser.add_argument("--timeout", type=int, default=90, help="Seconds per old/new MTSA compilation.")
    parser.add_argument("--java", default="java")
    parser.add_argument("--javac", default="javac")
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    jar = args.jar.resolve(strict=True)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    model = fetch(output / "inputs/Workflow_FG.lts")
    classes = output / "classes"
    classes.mkdir()
    subprocess.run([args.javac, "-cp", str(jar), "-d", str(classes),
                    str(HERE / "java/CompilePublicModel.java")], check=True, timeout=60)
    report = {
        "kind": "new MTSA generation and record-checking run",
        "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source_sha256": digest(model), "mtsa_jar_sha256": digest(jar),
        "heap": args.heap, "timeout_seconds": args.timeout, "configurations": [],
    }
    checkpoint = output / "native-exports.json"
    for n in args.jobs:
        folder = output / f"n{n}"
        folder.mkdir()
        derived = folder / "Workflow_derived.lts"
        derived.write_text(source(model, n))
        row = {"first_stage_jobs": n, "source_sha256": digest(derived), "exports": {}}
        for version, target in (("old", "OldEnvironmentAndController"), ("new", "NewEnvironmentAndController")):
            aut = folder / f"{version}.aut"
            command = [args.java, f"-Xmx{args.heap}", "-cp", os.pathsep.join((str(jar), str(classes))),
                       "CompilePublicModel", str(derived), target, str(aut)]
            started = time.perf_counter()
            with (folder / f"{version}.stdout").open("wb") as stdout, (folder / f"{version}.stderr").open("wb") as stderr:
                try:
                    result = subprocess.run(command, stdout=stdout, stderr=stderr, timeout=args.timeout)
                    status = result.returncode
                except subprocess.TimeoutExpired:
                    status = f"timeout{args.timeout}"
            entry = {"exit": status, "wall_seconds": time.perf_counter() - started}
            if status == 0:
                entry.update(header=aut.open().readline().strip(), sha256=digest(aut))
            row["exports"][version] = entry
        report["configurations"].append(row)
        checkpoint.write_text(json.dumps(report, indent=2) + "\n")
    successful = [row["first_stage_jobs"] for row in report["configurations"]
                  if row["first_stage_jobs"] <= 6 and all(e["exit"] == 0 for e in row["exports"].values())]
    if successful:
        report["record_validation"] = verify(output, output / "record-check", successful)
    report["finished_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    checkpoint.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    if any(e["exit"] != 0 for row in report["configurations"] for e in row["exports"].values()):
        raise SystemExit("At least one MTSA build failed or timed out; partial results were saved.")


if __name__ == "__main__":
    main()
