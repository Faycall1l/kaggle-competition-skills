# The +0.035 credited to conservation smoothing is confounded; measured locally the pass is negative on both terms

Date: 2026-10-26
Competition: 2026-ieee-big-data-traffic-flow-bench
Finding: L-030 credits the 5-iteration / blend-0.5 spatial flow diffusion with ~+0.035 LB "through the LWR conservation term". That credit came from v50nocons (LB 0.74440 vs champion 0.77944), which changed **two** things: it dropped the smoothing *and* rebuilt the state instead of using the stored `state_hw12.csv` champion artifact. The attribution is therefore not single-variable, and the local arithmetic does not support it.

Measured with the new truth-relative LWR instrument (L-034, `src/physics_local.py`), same June 21-30 holdout, official arithmetic:

| panel | field | S_state | S_LWR | S_physics |
|---|---|---|---|---|
| D12_I5_N | hw12 shipped | - | 0.492 | 0.658 |
| D12_I5_N | hw12 + conserve | - | 0.445 | 0.627 |
| D12_I5_N | HGB model | 0.9350 | 0.515 | 0.674 |
| D12_I5_N | HGB + conserve | 0.9333 | 0.491 | 0.658 |
| D7_I405_N | hw12 shipped | - | 0.491 | 0.654 |
| D7_I405_N | HGB + conserve | - | 0.530 | 0.681 |

Conserve costs 0.016-0.031 S_physics and 0.0017 S_state on the same field, i.e. about -0.004 overall by local arithmetic — the opposite sign to the +0.035 it is credited with. The empty-road guard, the other candidate explanation, is ruled out: minimum submitted flow is 485 vph and the share of submitted flows below 50 vph is 0.0000 with or without smoothing, so `S_FD` cannot collapse from 0.99 to 0.

Two readings remain, and one controlled submission decides between them: either the earlier +0.035 was the *state rebuild* rather than the smoothing, or the truth-relative LWR instrument mis-ranks the pass (its one unverifiable assumption is that the organizer's projection makes truth exactly residual-free, which the S_LWR = 1.0000 truth check supports). Until then conserve stays in the pipeline only because it was in the last shipped submission, not because it is measured positive.
Evidence: L-034, `.runs.jsonl` attempt 11 (v50nocons, two variables), `src/physics_local.py` on `out/state_train_*_hw12{,_cons}.csv` and `out/model_*_2030_06{,_cons}.csv`.
Applies when: re-attributing a leaderboard delta. A "rebuilt vs stored artifact" experiment is not a single-variable experiment for whatever post-pass the rebuild also toggled.
