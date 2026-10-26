# The scored split keeps its observed cells, so state can be measured on it without any answers

Date: 2026-10-26
Competition: 2026-ieee-big-data-traffic-flow-bench
Finding: There is no March truth on disk, but `data/val/*/mask_regime=*/*.parquet` is the *masked* validation layer, and the release only blanks the cells it scores. Everything still observed in that file is truth. So the scored distribution can be measured directly: take a validation day, blank a matched share of its still-observed cells using the release's own geometry (one- or two-step runs, never a whole cross-section), predict them with the shipped pipeline, and score against the values that were there.

That produces a leak-free, month-correct measurement of any state variant before spending a submission slot. It also fixes the two covariance problems that made every earlier instrument ambiguous: the synthetic blanks are on the same month as the scored split, and the rule is scored under exactly the same conditions as the model, so the *edge* is measured rather than inferred.

Protocol details that matter:

* Add the extra blanks on top of the release masks (`--extra 0.20` of still-observed cells) rather than targeting a total density. Topping up to a fixed total leaves R3 days (already 50% blank) with nothing to score and silently drops a third of the regime macro.
* Normalise flow by lanes with `station_lanes` from the baseline, exactly as `score_task1` does, or every S comes out ~0.1 too low.
* The local copy of the release carries `train/mainline_states_masked` for only three of eight panels (D12_I5_N, D7_I210_W, D7_I405_N). `src/synth_masks.py` writes stand-in masks for the rest with the release's geometry and density; they are used for fitting only, never for scoring.
* The June control must exclude the fit days, and with the shipped even-sample (`stems[::step][:12]`) the June 21 and 26 partitions *are* in the fit set — pick control days from the complement.

Costs about 15 minutes for all eight panels (fit + predict + score), single process.
Evidence: `src/state_valtest.py`, `src/synth_masks.py`, `out/logs/valtest_pool_mar.log`.
Applies when: a submission must be chosen between variants and the scored split has no labels. If the release masks only the scored cells, the observed remainder is a free validation set — check that before modelling anything else.
