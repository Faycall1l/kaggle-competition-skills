# LWR charges the *level* error of density, and swings 1.6x per unit of S_state

Date: 2026-10-26
Competition: 2026-ieee-big-data-traffic-flow-bench
Finding: `e_lwr = sum|dN_ours - rhs| / sum|rhs|`, and on both splits `rhs` is the truth's own accumulation change (`rhs = dN_true`): the organizer projects boundary flux onto the released observations, and the scorer substitutes truth for every non-target cell. Write the level error as `dN = N_ours - N_true`. At an interval whose downstream end is a target and upstream end is truth, the residual is exactly `-dN(t)`; at an interval with one target endpoint it is `|dN|` at that endpoint, and it is the *difference* of the error only when both ends are targets. Since targets sit in short runs, LWR is therefore a level-accuracy measure on density, divided by the typical 5-minute change in accumulation.

So LWR is not independently optimisable, and it moves faster than S_state because the denominator is small. Measured on D12_I5_N, December, official arithmetic:

| submission | S_state | S_LWR | S_physics |
|---|---|---|---|
| shipped rule | 0.8997 | 0.5047 | 0.6663 |
| model | 0.9305 | 0.5529 | 0.6989 |
| model + conserve(5, 0.5) | 0.9330 | 0.5337 | 0.6861 |

A +0.031 S_state gain bought +0.048 S_LWR. The effective weight of a state improvement is therefore about `0.35 + 0.15*(2/3)*1.56 = 0.51`, not 0.35. Scale that with panel: the model's +0.0145 on the scored month is worth ~+0.0075 overall, not +0.0051.

Two corrections:

* L-034's "no-change floor of 0.64" is wrong. A state that does not change in time has `dN_ours = 0`, so `e_lwr = 1` and `S_LWR = 0`. The 0.6663 measured for the rule is not a floor — it is the level-error of the rule under this normalisation, and it will fall as the state gets more accurate.
* `conserve.py` is a spatial flow diffusion, not a conservation solve. It *lowers* S_LWR (0.5529 -> 0.5337) while buying +0.0025 S_state, i.e. net negative on this scene — consistent with L-035, and it means the +0.00125 leaderboard move from adding it to v56 was noise. Do not read conserve as a physics lever.

Consequence: the physics term (0.15 weight) has no separate handle. It is a derivative of state accuracy with a ~1.56x gain, so every state improvement is worth about 1.5x its nominal weight and there is nothing to tune on Task 3 except the state itself.
Evidence: `out/logs/phys_dec_pair.log` (rule 0.6663 / model 0.6989 / model+conserve 0.6861), `src/physics_local.py`, `data/baseline/src/task3/score_task3.py`.
Applies when: a physics-style consistency metric is derived from the submission itself. Check whether the normaliser is the truth's own residual — if it is, the term is a rescaled accuracy measure, not an independent objective.
