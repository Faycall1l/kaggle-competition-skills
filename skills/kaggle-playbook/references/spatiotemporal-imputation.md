# Spatiotemporal Imputation and Forecasting Reference

Method ladder for sensor-network reconstruction (speed, flow, occupancy) and
short-horizon forecasting (queue propagation, demand estimation). Ordered by
implementation cost. Each level states when it wins, per benchmark evidence.

## Reconstruction ladder (Task 1 class: blanked cells, masked regimes)

### L0 — Historical profile (baseline)

Weekday by time-of-day mean per link from unmasked history. Wins when the
target day resembles its calendar peers and nothing else is used. Loses
everything available on the day itself: neighbouring links, same-link
observations an hour away, visible queue geometry.

### L1 — Temporal interpolation

For each blanked cell, interpolate between the nearest observed same-link
cells backward and forward in time (linear or Kalman-smoothed). Wins on
isolated outages (single detector, short gaps) where neighbours add little.
Costs one pass over the masked frame; no topology needed.

### L2 — Topology-aware neighbor blending

Combine L0/L1 with upstream and downstream link values at the same timestamp,
using the network topology (`lwr_mainline_topology.csv`: which link feeds
which). Weight by availability and by regime: free-flow propagates downstream
information upstream weakly; congested regimes propagate queue state upstream
strongly. Wins whenever the outage spans a detector but adjacent detectors
report — the common R1/R2 case. Requires the topology file and a per-link
availability mask.

### L3 — State-space filtering

Per-link Kalman filter (structural or CTM-based) fusing profile prior,
temporal dynamics, and neighbour observations with measurement-noise weighting
from `pct_observed`. Wins under heavy masking (R3, 50%) where static blending
has too few simultaneous observations. Costs parameter calibration
(process/measurement noise) per link or per link class.

### L4 — Graph and generative models

Inductive GNN kriging (message passing over the detector graph), low-rank
tensor completion, or conditional diffusion imputation. Wins on large-scale
sparse regimes where local methods starve; loses on cost and tuning time.
Evidence: on sparse graphs simple GNNs match complex ones; under dense
block-missing, global low-rank methods beat local ones. Attempt only after L2
scores are banked and versioned.

## Selection matrix

| Condition | Preferred level |
|---|---|
| Isolated short gaps, dense neighbours | L1, then L2 |
| Regime R1/R2 (20–30% masked) | L2 |
| Regime R3 (50% masked) | L3, consider L4 |
| Sparse neighbourhood, rich history | Global/low-rank (L4 family), not local GNN |
| Physics score matters | Any level constrained by the fundamental diagram (free speed, capacity, jam density per link); clamp outputs to feasible ranges |

## Queue forecasting (Task 2 class: 60-minute history, 30-minute horizon)

1. **Persistence** (baseline): repeat queue state at forecast origin. Loses
   every onset (history shows no queue, horizon has one).
2. **Shockwave-propagated persistence**: estimate wave speed from the history
   (speed-drop propagation delay between adjacent detectors), advect the
   observed queue boundary forward 30 minutes. Onset detection from upstream
   deceleration trend: decelerating upstream with no visible queue is the
   onset precursor. This is the first upgrade worth implementing.
3. **Cell-transmission update**: discretize links into cells, step density
   forward with demand from ramp counts and capacity from link parameters.
   Wins on ongoing conditions with long horizons; costs calibration.

## Demand and path-flow estimation (Task 4 class)

1. **Regularised non-negative least squares** (baseline): `||Af − c||² +
   λ||f − b||²`, `f ≥ 0`. Tune `λ` against the locally computable component
   (`S_link` from released counts); do not tune against the reference solve
   over released data (scores perfect locally, means nothing).
2. **Generalised least squares / path-flow estimators**: weight by
   measurement reliability (`pct_observed`), add destination-attraction terms.
3. **Bi-level refinement**: only when a fast assignment solver is available;
   rarely worth it before L1–L2 reconstruction gains are banked.

## Validation protocol

- Tune exclusively on splits with released answers (`train` here). Never tune
  against a reference solve built from the same released data being scored.
- Masked self-supervision: mask observed cells, recover them, compare. Match
  the mask regime distribution (R1/R2/R3) when sampling masks.
- Lock the fold/template definition before comparing methods; the scored row
  set is the template, not every blank cell.
