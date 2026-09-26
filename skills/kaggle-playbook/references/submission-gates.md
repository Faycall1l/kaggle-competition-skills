# Submission Acceptance Criteria

A result is submittable only when every applicable criterion below holds.
Evaluate in order; stop at the first failure and fix it before proceeding.

## 1. Format conformance

- Submission file header matches `sample_submission.csv` exactly (column names
  and order). Row count and key coverage match the test set.
- Code competitions: the submitted kernel version produced the file in its
  recorded run; no manual post-editing of outputs.

## 2. Validation agreement

- Mean out-of-fold score supports the change; fold variance is reported.
- No selection on public-LB movement alone. An LB improvement without CV
  agreement requires a diagnosed cause (distribution shift, metric mismatch)
  documented before submission.

## 3. Reproducibility

- Random seeds fixed across Python, NumPy, and model libraries.
- Run ID recorded with config, code version, data version, and artifact paths.
- Stackers trained exclusively on out-of-fold base predictions.

## 4. Compliance

- Competition rules permit all data sources, pretrained weights, and packages
  used. External data explicitly allowed or absent.
- Private artifacts (checkpoints, intermediate datasets) remain private unless
  publication is intended and permitted.
- `submission-limits` confirms remaining allowance; the cost of this attempt is
  stated to the user before sending.

## 5. Execution readiness (code competitions)

- Kernel metadata has `enable_internet=false`.
- Data sources attached in metadata; inputs located via recursive search, not
  hardcoded paths.
- A rerun from scratch reproduces the submission file byte-identical.
