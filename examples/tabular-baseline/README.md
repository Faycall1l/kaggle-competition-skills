# Tabular baseline example (titanic)

The exact notebook pushed in the E3 live eval: logistic regression on 6
features, CPU, private, `competition_sources: ["titanic"]`.

## Run it

1. Replace the `id` owner in `kernel-metadata.json` with your Kaggle username.
   The server normalizes owner to your account; a foreign handle fails status
   polling until `kernel_push.py` resolves it.
2. `python ../../skills/kaggle-cli-ops/scripts/kernel_push.py --dir .`
3. Expect: `COMPLETE`, train accuracy ~0.80, `submission.csv` (418 rows +
   header `PassengerId,Survived`) in kernel output.

## Verified behavior (E3, 2026-09-26)

- Data mounted at `/kaggle/input/competitions/titanic/train.csv` — the
  notebook locates it with `Path('/kaggle/input').rglob('train.csv')`.
- Public score of the produced file: `0.75598` (E4).
