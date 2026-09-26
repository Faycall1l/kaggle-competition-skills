# Traffic Flow v2 (Task 1 neighbor-augmented reconstruction)

L1/L2 reconstruction per `skills/kaggle-playbook/references/spatiotemporal-imputation.md`:
temporal interpolation first, topology-neighbor blending second, profile
fallback last, speeds clamped to link free speed.

## Files

- `task1_v2.py` — submission builder with the same CLI contract and output
  columns as the v1 baseline builder. Needs the baselines `src/` tree
  importable (`PYTHONPATH` at the cloned
  `trafficflowbench-public` repository, or the kernel bundle shipping `src/`).
- Fixture unit tests: `tests/test_task1_v2.py` (no data package needed).

## Run on Kaggle

Ship `task1_v2.py` in the kernel bundle next to `src/` and `config/`, attach
the competition data, and run:

```bash
python task1_v2.py --release-root <kaggle_public> --split validation --output state_v2.csv
```

Validate on `train` (answers released) with `score_task1.py` before
submitting; compare against the L0 baseline per panel and regime.
