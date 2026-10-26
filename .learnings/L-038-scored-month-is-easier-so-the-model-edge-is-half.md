# The scored month is easier for the persistence rule, so the state model's leaderboard edge is +0.015, not +0.030

Date: 2026-10-26
Competition: 2026-ieee-big-data-traffic-flow-bench
Finding: The HGB imputer beats the shipped temporal-neighbour rule by +0.036 S_state on a same-month holdout, and by +0.036 again on a six-month seasonal gap (June fit, December test). It beats it by only +0.015 on the month that is actually scored (2031-03). The loss is not seasonal drift and not a pipeline defect: 2031-03 is simply an easier month for the rule (0.918 vs 0.890), so there is less for the model to add.

Measured with the official arithmetic (`src/state_season.py` for the seasonal test, `src/state_valtest.py` for March):

| scene | fit | rule | model | edge |
|---|---|---|---|---|
| D12_I5_N, June 21-30 holdout | June 1-20 | 0.9012 | 0.9371 | +0.0359 |
| D12_I5_N, December 1-31 | June 1-20 | 0.8987 | 0.9347 | +0.0360 |
| D12_I5_N, March (real cells, +20% blanks) | shipped, solo | 0.9182 | 0.9289 | +0.0107 |
| D7_I405_N, March | shipped, pooled | 0.8588 | 0.8917 | +0.0329 |
| D7_I210_W, March | shipped, pooled | 0.8868 | 0.8867 | -0.0002 |
| all 8, March (3 usable) | shipped, pooled | 0.8879 | 0.9024 | +0.0145 |

At the state weight, +0.0145 is +0.0051 on the leaderboard, and the observed v55->v56 move was +0.00125 for conserve plus roughly +0.004 for the model. The unexplained 7x gap between the panel instrument and the leaderboard is closed; there was never a bug to find.

Two corrections to earlier notes:

* The stored 0.897277 "train S_state" is the score of the *rule* (hw12 + conserve) on train, not of the model. The shipped model scores ~0.93 there. Comparing the model's leaderboard effect against 0.897 was comparing against the wrong baseline.
* `src/mask_audit.py`'s first output ("validation masks are 2-3x looser: 73-86% of targets have a neighbour within 30 min vs 98.8%") was an artefact: the train sample was four R1 files while the validation sample spanned R1/R2/R3. Matched by regime the geometry is identical — median run 1 step, p90 2-3, no whole-cross-section blanks, in both splits. Blank *density* (20/30/50%) is the only difference, and it is the same in both splits.

Consequence: state headroom on the scored split is 0.926 -> ~0.96 = +0.034 S_state, worth roughly +0.017 leaderboard once the LWR coupling (L-040) is counted. That is a real but small prize; it cannot by itself produce the +0.06 that top-50 needs.
Evidence: `out/logs/state_season_dec.log`, `out/logs/valtest_pool_mar.log`, `out/valtest_*.csv`, `src/state_season.py`, `src/state_valtest.py`.
Applies when: a local holdout looks much better than the leaderboard. Before blaming the pipeline, measure the *rule* on the scored distribution too — the model's edge, not its absolute score, is what the leaderboard can credit.
