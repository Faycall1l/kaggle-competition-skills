# Code-competition example (titanic)

Same baseline as `../tabular-baseline`, submitted as a file competition entry
in the E4 live eval.

## Run it

1. Download kernel output (`submission.csv`) via
   `python ../../skills/kaggle-cli-ops/scripts/kernel_push.py` + output step,
   or `kaggle kernels output <owner/slug>`.
2. Preflight and submit:
   `python ../../skills/kaggle-cli-ops/scripts/comp_submit.py titanic --file submission.csv --message "<message>"`.
   Preflight checks allowance (`submission-limits --json`), header conformance,
   and kernel internet state for code paths.
3. Code-competition API submit may return 403 (`kernelSessions.get` scope);
   the script degrades to an explicit browser-submit instruction.

## Verified behavior (E4, 2026-09-26)

- Submission ref `56565709`, `COMPLETE`, public score `0.75598`.
- The `Submission ref:` print exists on upstream main only; pip releases need
  the description-match fallback (`ref_by_description`).
