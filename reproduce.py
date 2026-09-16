"""Reproduce the core finite studies without replacing the archived results."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
CORE_FILES = [
    'examples/transfer.py',
    'examples/exit_sets.py',
    'experiments/validate_composition.py',
    'experiments/validate_policy_search.py',
    'src/progress_reuse/__init__.py',
    'src/progress_reuse/graph.py',
    'src/progress_reuse/composition.py',
]
COMMANDS = [
    ['examples/transfer.py'],
    ['examples/exit_sets.py'],
    ['experiments/validate_composition.py', '--cases', '5000', '--seed', '20260910'],
    ['experiments/validate_policy_search.py'],
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'outputs/core',
                        help='Destination for fresh results (default: outputs/core).')
    args = parser.parse_args()
    destination = args.output_dir.resolve()
    archive = (ROOT / 'results').resolve()
    if destination == archive or archive in destination.parents:
        parser.error('Choose an output directory outside the archived results/.')

    # Historical scripts write to their own results/ directory. Running unchanged
    # copies in isolation preserves the publication evidence.
    with tempfile.TemporaryDirectory(prefix='progress-reuse-') as temporary:
        work = Path(temporary)
        for relative in CORE_FILES:
            copied = work / relative
            copied.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, copied)
        for command in COMMANDS:
            run = subprocess.run([sys.executable, *command], cwd=work,
                                 capture_output=True, text=True)
            if run.returncode:
                sys.stdout.write(run.stdout)
                sys.stderr.write(run.stderr)
                destination.mkdir(parents=True, exist_ok=True)
                if (work / 'results').exists():
                    shutil.copytree(work / 'results', destination, dirs_exist_ok=True)
                raise SystemExit(run.returncode)
            print('PASS', command[0], flush=True)

        results = work / 'results'
        composition = json.loads((results / 'record_composition_results.json').read_text())
        search = json.loads((results / 'record_policy_search_results.json').read_text())
        summary = {
            'python': platform.python_version(),
            'platform': platform.platform(),
            'composition_cases': composition['counts']['cases'],
            'record_equality_checks': composition['counts']['record_equality_checks'],
            'start_state_checks': composition['counts']['start_state_checks'],
            'policy_search_games': search['cases'],
            'complete_policies': search['totals']['exhaustive_global_policies'],
            'realizable_in_bounded_class': search['totals']['realizable_instances'],
            'unrealizable_in_bounded_class': search['totals']['unrealizable_within_memoryless_class'],
            'source_sha256': {relative: hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
                              for relative in sorted([*CORE_FILES, 'reproduce.py'])},
            'interpretation': 'Finite implementation checks, not proof or an end-to-end speed comparison.',
        }
        expected = json.loads((ROOT / 'results/SUMMARY.json').read_text())
        for key in ['composition_cases', 'record_equality_checks', 'start_state_checks',
                    'policy_search_games', 'complete_policies', 'realizable_in_bounded_class',
                    'unrealizable_in_bounded_class']:
            assert summary[key] == expected[key], (key, summary[key], expected[key])
        (results / 'SUMMARY.json').write_text(json.dumps(summary, indent=2) + '\n')
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copytree(results, destination, dirs_exist_ok=True)
    print(json.dumps(summary, indent=2))
    print(f'Results: {destination}')


if __name__ == '__main__':
    main()
