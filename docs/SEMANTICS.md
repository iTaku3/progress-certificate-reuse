# Semantics of the preliminary model

The model is a finite directed graph after a control policy has been fixed.
Each state carries a bit mask for the justice conditions that hold there.
`all_bits` denotes the conjunction of all conditions. Completing states are
absorbing and unsafe states are designated explicitly. A deadlock has no fair
infinite extension.

The three checked properties at the starting state are:

- Safety: no reachable unsafe state.
- Conditional completion: every infinite execution satisfying every GF
  justice condition eventually reaches completion.
- Nonconflictingness: from every reachable state, there remains an infinite
  execution satisfying all GF conditions under the same fixed policy.

These are not guarantees that the environment will in fact respond. They are
conditional guarantees plus a check that the chosen policy does not make its
own environmental assumptions impossible to fulfill.

For an internal state `v` without an internal fair continuation, let `E(v)` be
the exits reachable before encountering another boundary port. Let `G` be the
ports with a fair continuation in the composed system. The necessary exit
obligation is `E(v) ∩ G ≠ ∅`. It is checked for each internal state reachable
from a reachable entry. Keeping inclusion-minimal exit sets preserves this
test, including the empty set. Boundary states themselves also need a fair
continuation.

The record must include the meaning of monitor values and policy memory in
the surrounding modeling discipline. Equal untyped record data alone cannot
justify changing the meaning of an accepted request, a fairness condition or
a memory state. Deriving and checking those preservation conditions for
general updates is part of the remaining research.
