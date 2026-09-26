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
| Temporal ordering | Time split or expanding window; never random |
| Same source in text/image duplicates | Group by source key |
| Tiny datasets | Repeated K-fold; keep selection discipline strict |

## Metric implementation

- Reproduce the competition metric in code before modeling: clipping bounds,
  transforms (e.g. log), averaging mode (macro/micro), thresholds, sample
  weights. Verify against the sample submission format.
- Threshold-dependent metrics require threshold selection on out-of-fold
  predictions, never on test predictions.

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
