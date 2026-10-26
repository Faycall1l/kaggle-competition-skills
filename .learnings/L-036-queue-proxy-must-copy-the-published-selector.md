# The queue instrument must copy the published selector, not an approximation of it

Date: 2026-10-26
Competition: 2026-ieee-big-data-traffic-flow-bench
Finding: The July queue proxy was measuring a task the leaderboard does not pose. `config/synthetic_release_v1.json` publishes the selector: 5 `queue_onset` + 5 `queue_ongoing` windows per panel and split, `requires_queue_in_horizon`, `minimum_spacing_minutes 360`, and `condition_rationale`: "queue_onset holds windows whose visible history has no queue and whose horizon does; queue_ongoing holds windows where a queue is already visible". It also carries `maximum_persistence_iou 0.9`, a selector safeguard against windows a persistence forecast would ace. The five released D12_I5_N ongoing windows measure persistence IoU 0.099 / 0.537 / 0.551 / 0.576 / 0.621, i.e. they are all far from static.

The old proxy had two classes too many and the wrong selection rule: it split ongoing into `persist`/`dev` and took the **median origin of the longest fully-queued run**, which yields near-static windows (persistence IoU 0.91). It also kept a `dev` class (no queue at the origin) that the contract assigns to neither condition. Rebuilt `src/queue_windows.py` to emit exactly `queue_onset` (no queued cell in the 12-step history, none in horizon steps 0-4, ≥1 on step 5) and `queue_ongoing` (≥1 queued cell at the origin, queue on every horizon step, persistence IoU ≤ 0.9), one window per day. July proxy: 28+28 / 31+31 / 31+31 windows over D12_I5_N, D7_I405_N, D7_I210_W with ongoing persistence IoU 0.611 / 0.612 / 0.699.

With that instrument the shipped recipe is reproducible and near its ceiling. Recipe recovered from the kernels (`traffic-v26-queue-condition-models`, `traffic-v54-queueprior`): `task2_ml train --feature-set v4 --label-mode single --class-balanced --split-by-condition --stride 24 --max-origins 2400 --max-iter 400 --learning-rate 0.05 --max-depth 5` then `predict --threshold 0.35 --onset-rule` then the static onset prior (`k_rel_floor 0.5`, `k_max 12`). Trained on June only (`data/proxy_q_tr`), predicted July:

| variant | S_onset | S_ongoing | mixture (0.5/0.5) |
|---|---|---|---|
| model, no prior | 0.1625 | 0.9133 | 0.5379 |
| model + onset prior, thr 0.35 | 0.5823 | 0.9133 | 0.7478 |
| model + onset prior, thr 0.40 | 0.5823 | 0.9164 | 0.7493 |
| prior + count-matched top-k per step | 0.5823 | 0.5629-0.8355 | ≤ 0.7089 |
| prior + persistence union | 0.5823 | 0.9128 | 0.7475 |

Two consequences. First, the mixture 0.748 closes the leaderboard algebra: 0.82060 = 0.35·0.8973 (state) + 0.30·0.7478 (queue) + 0.15·0.66 (physics) + 0.20·S_ODME forces S_ODME ≈ 0.916. Every term is now accounted for, so the queue no longer hides an unmeasured gap. Second, the remaining queue headroom is small: the per-panel onset ceiling from the static ranking is 0.52 / 0.70 / 0.87 at the best k, and ongoing is already above the 0.9 heuristic (which only bounds persistence, not a model) at 0.913. Forcing per-step counts from the origin queue size, persistence unions and threshold moves all land inside ±0.004 mixture, i.e. inside the 0.006 retrain band.
Evidence: `data/proxy_q/task2` (180 windows, 247,764 truth rows), `out/q_jul_proba.csv`, `out/qgrid.csv`, `src/score_queue_proxy.py`, `src/qgrid.py`, `src/qjul_prior.py`, `data/rel/config/synthetic_release_v1.json`.
Applies when: building any local Task 2 instrument. The scored-window mixture and the selector's rejection rules are part of the metric; approximating them changes the measured score by more than any variant being tested.
