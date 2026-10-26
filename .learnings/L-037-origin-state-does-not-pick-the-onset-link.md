# Origin state does not pick which bottleneck queues; the static onset rate is still the best ranker

Date: 2026-10-26
Competition: 2026-ieee-big-data-traffic-flow-bench
Finding: Half of Task 2 is `queue_onset`, where the whole prediction is 1-6 links on the final step. The shipped rule ranks the panel's links by their June onset rate and takes the top k. That is nearly exact where one bottleneck dominates (D7_I405_N: 0.87 IoU with k=2) and close to a coin flip where several share the rate mass (D7_I210_W: 8 candidates between 0.17 and 0.35).

The release contract claims the case is solvable from the origin state: "an hour before a queue forms the road is already at 1.28x its queue threshold against 1.54x where none follows, and carries 6912 vph against 4620". Tested directly on the July proxy (`src/onset_rank.py`): restrict to the panel's historical onset candidates, label the links that actually queue on the final step, and score each origin signal by within-event AUC (0.5 = coin flip).

| panel | candidates/event | rate AUC (June) | rate AUC (July) | best origin signal AUC (July) |
|---|---|---|---|---|
| D12_I5_N | 4.6 | 0.833 | 0.636 | -fratio 0.644 |
| D7_I405_N | 8.7 | 0.960 | 0.989 | -occ 0.584 |
| D7_I210_W | 5.9 | 0.524 | 0.475 | -fratio 0.583 |

No signal generalises: flow ratio is the best ranker on D12 and the *worst* on D7_I405_N; speed ratio is inverted on D12 in June (0.277) and mildly positive in July (0.404). Blending any origin signal into the rate ranking, restricted to the candidate set with small weights (λ = 0.25/0.5/1.0 on rank-normalised scores), never beats the rate alone on any panel at any k: on D7_I405_N every λ degrades 0.702 → 0.110-0.680, on D12 0.521 → 0.390-0.488, on D7_I210_W the best blend ties (+0.02 at k=4, inside noise).

Conclusion: the origin observables in the contract describe *when* a queue is likely somewhere in the panel, not *which* link will be the first to break. The static rate already contains the link-level information. Onset headroom on this instrument is therefore ~+0.01 mixture at best, not the +0.2 that a working conditional ranker would have delivered. Do not re-open this without a new observable (e.g. a per-link signal not already in the June rate, such as incident flags or ramp demand).
Evidence: `src/onset_rank.py`, July proxy windows (28-31 onset windows per panel), `out/q_jul_proba.csv`.
Applies when: a task requires choosing among a handful of historically likely candidates. Measure within-candidate AUC first; a signal with cross-sectional AUC 0.7 can still be worthless for the within-set decision.
