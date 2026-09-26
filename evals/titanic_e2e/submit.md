# Titanic E2E — E4 submit transcript

Date: 2026-09-26. File: `/tmp/evals/output/submission.csv` (419 lines,
header `PassengerId,Survived`). Message: `kaggle-competition-skills E4 eval`.
Cost: 1 daily titanic submission (10 allowed, 10 remaining at preflight).

## Result

Submission **ref 56565709** — `SubmissionStatus.COMPLETE`, public score
**0.75598** (train accuracy was 0.7957; plausible public-LB gap).

## Preflight (verified live, read-only)

- `check_allowance('titanic')` passes after the flag/key fix below.
- `check_file` passes header rules against the local sample.

## Defect found and fixed

`send()` assumed the CLI prints `Submission ref: <ref>`. That print exists
only on upstream main; pip release 2.2.4 prints no ref line. The old fallback
returned raw output tail as the ref, so `poll()` compared garbage against the
submissions list, logged `unknown` 11 times, and never terminated (killed at
the 30-minute window; the submit itself had succeeded in seconds).

Fix (verified live, no slot spent):

- `send()` parses the ref line when present; otherwise resolves via
  `ref_by_description()` — newest row with exact description match.
  Raises instead of returning unparseable output.
- Live check: `ref_by_description('titanic', 'kaggle-competition-skills E4 eval')`
  → `56565709`; `submission_state('titanic', '56565709')` → `complete`.

## Gate

84 passed; black + mypy clean.
