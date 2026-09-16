# Progress Certificate Reuse

Reproducible **preliminary experiments** on records at component boundaries,
checking safety, conditional completion, and nonconflictingness during
controller updates. The repository also includes a separate Node-RED HTTP
experiment on observing the completion of asynchronous operations.

This is a finite research prototype. General state migration, finite-memory
synthesis, automatic dependency invalidation, and an integrated update engine
with demonstrated end-to-end speedup remain future work.

## Experiments and evidence

| Study | Checked scope | Location |
|---|---|---|
| Fixed-policy record composition | 5,000 generated graph triples; 20,000 record-equality checks and 20,720 start-state checks agree with direct reconstruction/full-state checking | [Core protocol](docs/EXPERIMENTS.md), [archived results](results/SUMMARY.json) |
| Bounded memoryless policy search | 120 games, 7,680 complete policies, and 474 record representatives agree; 5 games realizable and 115 unrealizable in this bounded class | [Search implementation](experiments/validate_policy_search.py), [results](results/record_policy_search_results.json) |
| Workflow-derived models | New-version one-order fragments range from 17 to 737 states; re-recording the changed stage and checking all connections agrees with full reconstruction | [Workflow experiment](experiments/workflow/README.md) |
| Standard HTTP Request node | 36 artificial inputs × 3 methods; replay of 108 recorded conditions agrees with the original aggregate results | [HTTP experiments and trace replay](experiments/async-interface-contracts/README.md) |

The first two studies use generated finite graphs. The Workflow study uses a
model from the separate
[Fine-Grained Dynamic Controller Update via On-the-Fly Synthesis artifact](https://github.com/iTaku3/Fine-Grained-Dynamic-Controller-Update-via-On-the-Fly-Synthesis),
pinned to commit `cce6bf2204cda4396800217d23a9a57a5777aadf`.
That repository is the source of the model and MTSA tool, while this repository
contains the additional record-reuse experiments.

## Reproduce the core checks

Python 3.10 or newer is sufficient; the core checks use only the standard
library and do not access the network.

```sh
git clone https://github.com/iTaku3/progress-certificate-reuse.git
cd progress-certificate-reuse
python3 reproduce.py
```

Fresh results go to `outputs/core/`. The runner executes unchanged copies of
the experiment code in a temporary directory and checks the main totals against
the archived `results/SUMMARY.json`. The archived results are preserved.
To choose another output directory:

```sh
python3 reproduce.py --output-dir outputs/my-core-run
```

The following original commands are also available. They **replace their
corresponding archived files in `results/`**, so use a disposable checkout if
running them directly:

```sh
python3 examples/transfer.py
python3 examples/exit_sets.py
python3 experiments/validate_composition.py --cases 5000 --seed 20260910
python3 experiments/validate_policy_search.py
```

For model acquisition, Java/MTSA export, and record reconstruction, follow the
[Workflow instructions](experiments/workflow/README.md). For Node.js dependencies,
HTTP execution, and independent trace replay, follow the
[HTTP instructions](experiments/async-interface-contracts/README.md). Neither
additional study is run by the core `reproduce.py` command.

## What a record retains

Under a fixed policy, the environment may still choose among legal transitions.
Environment assumptions are conjunctions of `GF J_i` conditions, and completion
states are absorbing. At each boundary entry, a record retains:

1. Paths to other boundary ports and the monitor conditions seen along them.
2. Reachable internal fair cycles and reachable unsafe states.
3. Minimal families of exit sets for internal states that cannot satisfy all
   assumptions while remaining within the component.

Every exit-set obligation from every reachable entry must be satisfied. The
empty exit set matters: it represents a trapped internal branch. Both normal
records and records with completion states removed are needed to check
completion. The [semantics](docs/SEMANTICS.md) describe the three properties.

The composition function inspects records and connector edges. Initial record
construction still inspects internal graphs, and its cost can grow
exponentially with the number of ports or assumptions. New boundary entries
require reconstruction.

## Interpretation and limitations

- These finite comparisons are implementation evidence, not independent proofs.
  The full-state reference checker does not consume cached records and uses a
  different SCC computation, but the implementations may share modeling errors.
- Policies and memories are already expanded into states. The bounded search
  is memoryless with a fixed small number of choices.
- The Workflow partition and changed stage are supplied explicitly. Its timing
  measurements concern record processing after model construction and do not
  establish end-to-end update speedup. Timed-out configurations are retained.
- The HTTP study tests artificial workloads against a local mock server. It is
  preparation for observing completion, not a verification of arbitrary
  Node-RED flows or an integration of update synthesis with state migration.
- Repeating fixed seeds reproduces the same evidence; it adds no new cases.
  Elapsed times depend on the machine and are not comparative performance claims.

## Provenance and license

The core experiments were performed on 2026-09-10 and packaged on 2026-09-11;
the combined publication was prepared on 2026-09-16. Each additional study
keeps its own historical results, reproduction instructions, and provenance.
See [core provenance](PROVENANCE.json) and the subdirectory READMEs.
The [publication validation report](VALIDATION.json) summarizes the local
checks performed before publication. GitHub Actions reruns the core and HTTP
studies; the Workflow study requires the separately acquired MTSA jar.

Original code in this repository is distributed under the [MIT license](LICENSE).
Third-party models and the MTSA executable are acquired separately from their
upstream distribution; their original terms apply. Node-RED and its test helper
are installed through the pinned npm dependency lockfile and retain their own
licenses. No third-party model, MTSA binary, or installed npm dependency tree
is bundled in this repository.

## 日本語での概要

本リポジトリは、研究計画の準備状況に記載した次の試作・検証をまとめたものです。

- I・II：固定制御器5,000組の記録検査、記憶なし制御器7,680通りの探索。
- 公開受注モデルから作った新版17～737状態の例：変更部分の再記録と全接続検査。
- IIIの準備：標準HTTPノードの実行と、その履歴を別プログラムで照合する環境。

受注モデルの原本と従来研究の合成器は、上記の別リポジトリで公開されています。
ここでは、そのモデルを用いた追加検査と、新しい試作コードを公開しています。
一般の移送・有限記憶・自動失効を含む合成、および更新全体の高速化は未達成です。
