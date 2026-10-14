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
  documented before submission. Private LB is typically 70–100% unseen data —
  prefer the CV-trusted submission over the LB-maximizing one.
- Log CV mean±std and the CV–LB delta for every submission; track the
  correlation across experiments instead of hill-climbing one LB number.

## 3. Reproducibility

- Random seeds fixed across Python, NumPy, and model libraries. Average over
  multiple seeds before claiming a gain — a single-seed win is a lottery
  ticket, not evidence.
- Hold out one never-touch fold for the final gate; it is not used for
  tuning or selection until the shortlist is frozen.
- Run ID recorded with config, code version, data version, and artifact paths.
- Stackers trained exclusively on out-of-fold base predictions.

## 4. Compliance

- Competition rules permit all data sources, pretrained weights, and packages
  used. External data explicitly allowed or absent.
- Private artifacts (checkpoints, intermediate datasets) remain private unless
  publication is intended and permitted.
- `submission-limits` confirms remaining allowance; the cost of this attempt is
  stated to the user before sending. Typical allowance is ~5/day — keep the
  count low and select ≤2 final submissions rather than spraying attempts.

## 5. Execution readiness (code competitions)

- Kernel metadata has `enable_internet=false`.
- Offline rerun assumed: notebook re-executes top-to-bottom on hidden test
  data with no network. Bundle weights and packages via Kaggle Datasets/Models
  — no pip-install-from-internet at inference. All external data must be
  explicitly allowed by the Rules tab.
- Session budget fits the caps: ≤9h CPU/GPU runtime typical for code
  competitions (12h session max, 9h TPU); `/kaggle/working` holds up to ~20GB
  and persists only on Save & Run All.
- Data sources attached in metadata; inputs located via recursive search, not
  hardcoded paths.
- A rerun from scratch reproduces the submission file byte-identical.
