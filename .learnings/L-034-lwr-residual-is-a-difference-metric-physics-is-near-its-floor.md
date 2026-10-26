# The LWR residual is a difference metric: level bias is free, band-edge steps and 5-minute noise are not. Physics headroom is ~0.01 LB, not ~0.08

Date: 2026-10-26
Competition: 2026-ieee-big-data-traffic-flow-bench
Finding: `E_LWR` is recoverable locally after all, and doing so kills the belief that physics is the big reservoir.

**How it becomes measurable.** The organizer's boundary flux is documented as *projected onto the released observations so that a participant who reproduces what was published satisfies the conservation identity exactly*. On the train split the published field is the unmasked truth and the scorer substitutes truth for every non-target cell, so `rhs(t) = dN_true(t)` identically and

    E_LWR = sum|dN_ours - dN_true| / sum|dN_true|        (N = (q/v) * L)

Only the **time difference of our error** is charged. `src/physics_local.py` replicates the scorer's row filtering (observable links, ramp validity by mode, dt window) and reproduces S_FD bit for bit. Validation: feeding the truth as the submission gives S_LWR = 1.0000 and S_FD identical to the truth reference, exactly as the projection property requires.

**What it says.** D12_I5_N and D7_I405_N, June 21-30, official arithmetic:

| field | S_FD | S_LWR | S_physics |
|---|---|---|---|
| shipped hw12 rule | 0.990 | 0.492 | 0.658 |
| shipped + conserve 5/0.5 | 0.990 | 0.445 | 0.627 |
| HGB model (v56) | 0.991 | 0.515 | 0.674 |
| HGB + conserve | 0.991 | 0.491 | 0.658 |
| D7 shipped / model | 0.979 / 0.982 | 0.491 / 0.534 | 0.654 / 0.683 |

S_FD is saturated (~0.99) everywhere: the paired (speed, flow) fields already lie on the triangular diagram, and the empty-road guard never fires (minimum submitted flow 485 vph, share below 50 vph = 0.0000). So all of the physics loss is S_LWR.

**Why it cannot be fixed by reconstruction.** On R1, 87% of the residual mass sits on transitions with exactly one predicted endpoint (100,346 edge rows at mean |resid| 0.323) and only 13% on masked interiors (12,553 rows at 0.390). A constant level offset inside a band cancels out of a difference entirely, which is why the field can carry a 3-4% density bias and still score. But the residual per touched transition (0.33) is almost as large as the true 5-minute change itself (mean |dN_true| = 0.425, i.e. 2% of N), so at 5-minute resolution the field is only marginally better than predicting "nothing changes" (that floor is E_LWR ≈ 0.36). Reaching S_LWR 0.9 would require the level error to be ~0.1 units on N ≈ 20 — 0.5% — which no level-based imputer will deliver.

**Refuted idea, worth recording.** Band-edge anchoring (`src/edge_anchor.py`): force predicted density to equal the observed neighbour at each band edge with a linear ramp across the band, changing flow only so the speed field is untouched. It fails — S_LWR 0.5153 -> 0.5192 at half strength, 0.4395 at full strength, both panels. Forcing exact continuity replaces a small level error with an error of size |dN_true|, which is *larger*; the weekday/slot profile already tracks the 5-minute shape better than the continuity assumption does. A tail cap was the obvious follow-up, but the measured level error (mean |dN| 0.066 overall, 0.37 over targets) already shows the mechanism has nothing to gain.
Evidence: `src/physics_local.py`, `src/edge_anchor.py`, run log 2026-10-26.
Applies when: a physics/consistency term is a residual of a *differenced* quantity. Judge candidate post-processing on the difference, not the level; and do not spend effort on a term whose residual per scored cell is already at the scale of the signal's own step.
