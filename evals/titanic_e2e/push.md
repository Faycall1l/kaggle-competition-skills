# Titanic E2E — E3 push/status/output transcript

Date: 2026-09-26. Kernel: private CPU notebook, `competition_sources: ["titanic"]`.
Quota at start: GPU 30.00h / TPU 20.00h remaining.

## Push

```bash
python skills/kaggle-cli-ops/scripts/kernel_push.py --dir /tmp/evals/kernel
```

The server created `faycal00/titanic-eval-baseline` v1 and ran it to
`COMPLETE`. Wall time (queue + run): minutes; the script's backoff polling
covered it without manual intervention.

## Findings (all fixed in-repo, verified below)

1. **Owner normalization.** Metadata id used the GitHub handle
   (`Faycall1l/...`); the server normalizes owner to the Kaggle username
   (`faycal00/...`). Status on the metadata slug fails with a slug-mismatch
   error. Fix: `poll_status` resolves once via `kernels list -m` title match
   and reports `slug_normalized: true`.
2. **First-page miss.** Default `kernels list` ordering does not surface the
   newest kernel; resolution requires `--sort-by dateRun --page-size 100`.
3. **Stdout JSON pollution.** The key-permission warning prints to stdout,
   breaking `--format json` parsing. Fix: `common.extract_json` skips
   non-JSON preamble lines; `doctor.check_quota` uses it (quota now parses).

## Verification

- `kaggle kernels status faycal00/titanic-eval-baseline` → `COMPLETE`.
- Logs show mount at `/kaggle/input/competitions/titanic/train.csv`
  (confirms the rglob-over-hardcoded-path guidance), train accuracy
  `0.7957`, `418 rows` written to `/kaggle/working/submission.csv`.
- `kaggle kernels output ... -p /tmp/evals/output` → `submission.csv`
  (419 lines incl. header `PassengerId,Survived`) + run log.
- Post-fix live check: `poll_status('Faycall1l/titanic-eval-baseline', 1)`
  → `{"state": "COMPLETE", "kernel": "faycal00/titanic-eval-baseline"}`.
- Offline gate: 77 passed; black + mypy clean.

## Note

A duplicate push during diagnosis returned `409 Conflict` (same title) —
expected server behavior, no action needed.
