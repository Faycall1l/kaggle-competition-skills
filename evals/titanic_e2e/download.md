# Titanic E2E — E2 download transcript

Date: 2026-09-26. Auth: `~/.kaggle/access_token` (KGAT, mode 600).
CLI: pip release 2.2.4 (note: `--unzip` absent; script extracts manually).
Workspace root for eval: `/tmp/evals` (data kept out of the repo).

## Preflight

`doctor.py` reported credentials present (`file:access_token`,
`file:kaggle.json` with credentials) and correctly warned that
`~/.kaggle/kaggle.json` has mode `0o644`.

`kaggle competitions list --group entered` returned live rows, confirming
token validity.

## Download

Command:

```bash
python skills/kaggle-cli-ops/scripts/comp_init.py titanic --path /tmp/evals
```

Output (stdout, JSON):

```json
{"ok": true, "workspace": "/tmp/evals/titanic", "archive": "/tmp/evals/titanic/data/titanic.zip", "extracted": ["gender_submission.csv", "test.csv", "train.csv"]}
```

No stderr warnings. Duration: seconds (34KB archive).

## Verification

- `/tmp/evals/titanic/data/` contains `train.csv` (61KB), `test.csv` (28KB),
  `gender_submission.csv` (3KB) with expected headers
  (`PassengerId,Survived,Pclass,Name,...`).
- `submissions/` created empty; `README.md` contains the rules URL.
- No credentials appear in output or workspace.

## Finding

E2 passes. One script-side note applied: `comp_init.py` requires the `kaggle`
binary on `PATH`; `doctor.py` reports this correctly when absent.
