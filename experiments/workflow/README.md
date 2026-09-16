# Workflow record reconstruction: 17–737 states

This package reproduces the **restricted record-reconstruction experiment** on
the published order-processing Workflow model. The old controller allows billing
and shipping to overlap; the new controller waits for billing to finish before
starting shipping. Both controllers are first constructed by MTSA. We then follow
one accepted order until rejection or archiving, make these outcomes absorbing,
and compare rebuilding all records with rebuilding only the changed second stage.

The stage partition is supplied manually. Parallel behavior inside each stage is
retained. This is not a general update synthesizer, a state-transfer algorithm,
automatic dependency invalidation, or evidence of faster end-to-end updates.

## What is included

- `generate.py`: the original transformation adding parallel first-stage jobs.
- `measure.py`: the original episode extraction, record checks and timing loop,
  with portable imports and separate input/output directories.
- `java/CompilePublicModel.java`: our helper for exporting controllers with MTSA.
- `historical/`: original September 10–11, 2026 measurements. Five record-result
  files are byte-for-byte copies. In the two compilation manifests only command
  arrays were replaced with portable placeholders; numerical results are intact.
- `PROVENANCE.json`: pinned upstream URL, input hash, original source/result hashes
  and an explicit list of packaging changes.
- `VALIDATION.json`: publication-time checks, distinct from historical experiments.

The upstream model, its derived models, MTSA binary, AUT exports, and verbose logs
are **not included**. The source model is fetched from the fixed upstream commit
and checked against its SHA-256. Third-party licenses remain with their owners;
the repository license does not relicense MTSA or the downloaded model.

## Historical results

| First-stage jobs | New accepted-order episode states | Locally rebuilt states |
|---:|---:|---:|
| 2 | 17 | 5 |
| 3 | 35 | 5 |
| 4 | 89 | 5 |
| 5 | 251 | 5 |
| 6 | 737 | 5 |

For all five configurations, record-only composition agrees with direct checking
for safety, conditional completion, and nonconflictingness. Full and local record
reconstruction agree, while removing the archiving connector is detected as a
nonconflictingness failure. Every method checks all six boundary ports.

September 10 used a 2 GB JVM heap limit and 90 seconds per compilation: 2–5 jobs
completed; 6 and 7 jobs timed out. September 11 retained the same inputs but used
an 8 GB heap limit and 300 seconds: 6 jobs completed (742 old / 738 new native
states, then 741 / 737 episode states); 7 jobs timed out. These failed cases remain
in the historical manifests. The machine was a 24 GB MacBook Air with other
desktop applications active. A heap limit is not measured memory consumption,
and both memory and time limits changed between runs.

The six-job historical median was 37.418 ms for full reconstruction plus boundary
checking and 0.115 ms for local reconstruction plus boundary checking. This
excludes input reading, initial MTSA construction, state-transfer checking,
candidate search and the full-graph oracle. It is not end-to-end update speedup.
Fresh timings depend on the machine and must not be expected to match these values.

## Reproduce from the upstream model

Use Python 3.10+ and a JDK with `java` and `javac` on `PATH` (the helper uses Java
11 APIs). The exact MTSA jar used for the historical and publication-time runs
is available as the upstream [v1.0.0 `mtsa.jar` release asset](https://github.com/iTaku3/Fine-Grained-Dynamic-Controller-Update-via-On-the-Fly-Synthesis/releases/download/v1.0.0/mtsa.jar)
(about 349 MB). Its SHA-256 is
`f805413e8665c53bdc210a4092aea5bf7ca1055ee973cd1ce2535491cb04f3e5`,
also recorded in `PROVENANCE.json`. Supply this jar to `--jar`; compatibility
with every MTSA release has not been established.
Run these commands from the repository root after installing the core package
or directly from the source checkout:

```sh
# Small complete run: fetch, compile old/new controllers, then check all records.
python3 experiments/workflow/run.py --jar /path/to/mtsa.jar \
  --jobs 2 --heap 2g --timeout 90 --output outputs/workflow-smoke

# Original September 10 successful configurations.
python3 experiments/workflow/run.py --jar /path/to/mtsa.jar \
  --jobs 2 3 4 5 --heap 2g --timeout 90 --output outputs/workflow-2-to-5

# Extended six-job run; initial MTSA construction can take several minutes.
python3 experiments/workflow/run.py --jar /path/to/mtsa.jar \
  --jobs 6 --heap 8g --timeout 300 --output outputs/workflow-6
```

To repeat the seven-job capacity probe, use `--jobs 7 --heap 8g --timeout 300` and
a new output directory. A timeout is saved and causes a nonzero exit; it is not
silently omitted. There is no historical successful seven-job reference, so this
probe only compiles and reports outcomes. `--java` and `--javac` accept explicit
executables. Every run requires a new output directory and leaves historical data
unchanged. Generated inputs/outputs are local files and should not be committed.

To check existing exports without rerunning MTSA, arrange them as
`exports/n2/old.aut`, `exports/n2/new.aut`, …, `exports/n6/new.aut`, then run:

```sh
python3 experiments/workflow/verify_exports.py --input exports \
  --jobs 2 3 4 5 6 --output outputs/workflow-record-replay
```

This reruns direct-graph and record checks, checks the negative control, and
compares every non-timing field with the historical result. A mismatch fails the
run. `validation.json` identifies this as a new record-checking run on supplied
exports; it does not claim that MTSA generation was repeated.

## Input provenance

The upstream input is
[`Experiment/Models/Workflow_FG.lts`](https://github.com/iTaku3/Fine-Grained-Dynamic-Controller-Update-via-On-the-Fly-Synthesis/blob/cce6bf2204cda4396800217d23a9a57a5777aadf/Experiment/Models/Workflow_FG.lts),
commit `cce6bf2204cda4396800217d23a9a57a5777aadf`, SHA-256
`4c7e69a25385ad63a7458a3f5b5c70c241bb8edbb79041dde22be9e3e025247d`.
The generator uses the same first 154 source lines and exact substitutions as
the historical experiment. Source-version changes fail checksum verification.
