# Validation Design Reference

Fold selection, metric implementation, and leakage checks. Read before any
feature engineering or model selection.

## Fold selection matrix

| Data condition | Strategy |
|---|---|
| Balanced classification | Stratified K-fold |
| Imbalanced classification | Stratified folds + threshold tuning on out-of-fold predictions |
| Regression, symmetric target | K-fold |
| Regression, skewed/multimodal target | Binned stratified folds |
| Repeated entities (user, patient, product) | Group K-fold on the entity key |
| Imbalanced + grouped (e.g. patients with rare events) | StratifiedGroupKFold — preserves class ratios within group boundaries |
| Temporal ordering | Time split or expanding window; never random. Use TimeSeriesSplit / GroupTimeSeriesSplit; add a purge gap + embargo when lag features can leak across the cutoff |
| Same source in text/image duplicates | Group by source key |
| Tiny datasets | Repeated K-fold; keep selection discipline strict |

## Metric implementation

- Reproduce the competition metric in code before modeling: clipping bounds,
  transforms (e.g. log), averaging mode (macro/micro), thresholds, sample
  weights. Verify against the sample submission format.
- Threshold-dependent metrics require threshold selection on out-of-fold
  predictions, never on test predictions.

## Adversarial validation gate

Before trusting a random split, test train vs test distribution:

1. Label train=0, test=1; run 5-fold LightGBM/logreg; report ROC-AUC.
2. AUC ≈ 0.5 → same distribution, random/stratified split stands.
3. AUC ≳ 0.7–0.8 → strong shift: switch to group/time/adversarial folds,
   drop or downweight drifting features, and do not select on public-LB
   movement until CV and LB agree again.

## Proxy metric vs decision metric gate

A gain on an offline proxy (per-row AUC, cell-level IoU, point RMSE) can invert
at the metric the leaderboard actually scores. Before acting on a proxy win:

1. Re-run the change at the **decision metric** — the granularity the scorer
   uses (window/group/conversation level), with the real threshold applied.
2. Only claim the gain if the proxy win survives step 1. A proxy win that
   vanishes or inverts is a calibration artifact, not a model improvement.
3. Hold every other component fixed so the delta is attributable.

Observed: an unweighted classifier beat balanced on proxy cell-level IoU
(0.588 vs 0.565) yet lost by ~0.11 at window IoU (0.424 vs 0.531), because it
under-predicted positives and recall collapsed under the decision threshold.
The proxy ranking was exactly backwards.

## Leakage checklist

- Target encodings computed out-of-fold with smoothing.
- Scalers, imputers, and feature selectors fit inside the fold boundary.
- No validation-row target visibility in any preprocessing step.
- Time-cutoff features use only data available at prediction time.
- Duplicate keys across train/test identified via group keys, not assumed absent.

## Out-of-fold discipline

- Persist the fold column in the training data; all experiments share it.
- Save out-of-fold predictions per model; they are the input to error analysis,
  threshold tuning, blending, and stacking.
- Report mean fold score and fold variance. A single best fold is not evidence.
- Stackers train exclusively on out-of-fold base predictions; Ridge is the
  default meta-learner. Use nested CV for second-stage blending.
