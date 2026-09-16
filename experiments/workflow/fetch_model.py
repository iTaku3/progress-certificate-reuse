"""Fetch the pinned upstream Workflow source after verifying its SHA-256."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

HERE = Path(__file__).resolve().parent
SOURCE = json.loads((HERE / "PROVENANCE.json").read_text())["source_model"]


def fetch(destination):
    destination = Path(destination)
    if destination.exists():
        content = destination.read_bytes()
    else:
        request = urllib.request.Request(SOURCE["url"], headers={"User-Agent": "progress-certificate-reuse"})
        with urllib.request.urlopen(request, timeout=60) as response:
            content = response.read()
    actual = hashlib.sha256(content).hexdigest()
    if actual != SOURCE["sha256"]:
        raise ValueError(f"Workflow source SHA-256 mismatch: {actual}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        destination.write_bytes(content)
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(fetch(args.output))
