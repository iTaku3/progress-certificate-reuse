# Core experiment protocol

This document describes the core experiments originally carried out on 2026-09-10. The
record construction, composition, checking and bounded-search functions were
preserved when making them standalone. `PROVENANCE.json` lists the preserved
functions and source digests. Import paths and output paths changed.

The fixed-policy generator uses seed 20260910 and 5,000 graph triples with
3–10 states per component, 1–4 boundary ports, and 0–3 GF conditions. It checks
both flat and nested composition, hiding intermediate ports where possible,
against records rebuilt from the complete graph. It also checks all selected
external starts using a full-state reachability-based reference checker.
Unsafe states, goal-avoiding fair cycles, empty exit obligations, and illegal
new entries are retained in the tests.

The bounded-policy generator uses seed 2026091027 and 120 games. Each game has
three 6-state components. Two controlled states in each component have two
choices each, giving 64 global memoryless policies per game. Environment
choices are retained. All final record classes, their three-guarantee verdicts,
and representative policies are compared with exhaustive enumeration.

The four commands in the README run independently of the application that
motivated this research. They use generated finite graphs only. No model was
selected or excluded based on execution time. The observed 5 realizable and
115 unrealizable games are both retained; the realizable subset is not used
as a success rate for general controller synthesis.

The implementation writes run times for reproducibility diagnostics. These
are validation times and should not be cited as comparative performance.
The stored outputs contain seeds, case counts and source digests. A rerun with
the same seeds is a replication, not additional validation cases.

## Publication runner and companion studies

The combined publication prepared on 2026-09-16 keeps these archived results
unchanged. `python3 reproduce.py` executes isolated copies of the original
core scripts and writes fresh results to `outputs/core/`. Only the runner and
publication documentation changed; the core algorithm files did not.

The [Workflow study](../experiments/workflow/README.md) and
[HTTP study](../experiments/async-interface-contracts/README.md) have separate
protocols, dependencies, provenance, and historical evidence. The core command
does not run those studies.
