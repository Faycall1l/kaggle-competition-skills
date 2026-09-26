---
name: kaggle-playbook
description: "Modeling judgment for Kaggle competitions: validation design, baseline ordering, and submission acceptance criteria. Use when choosing folds, metrics, model architectures, or deciding whether a result is submittable. Pairs with kaggle-cli-ops for execution."
license: MIT
compatibility: "No runtime requirements; methodology guidance only"
metadata: {"author": "Faycall1l", "version": "0.1.0"}
---

# Kaggle Playbook

## When to activate

- User asks how to validate: fold strategy, metric implementation, threshold selection.
- User asks what to build next: baseline ordering, architecture choices, ensemble decisions.
- User asks whether a result is ready: acceptance criteria before submission.
- Competition work where local CV disagrees with the public leaderboard.

## When NOT to use

- CLI execution (download, push, submit) — that is `kaggle-cli-ops`.
- Credential, quota, or failure diagnosis — see `kaggle-cli-ops` references.
- Generic ML tutorials with no competition target.

## Workflow catalog

| Task | Reference |
|---|---|
| Choose folds, implement metric, check leakage | `references/validation.md` |
| Verify a submission is ready | `references/submission-gates.md` |

## Instructions

1. Design folds before feature engineering. Persist the fold column so every
   experiment shares the comparison surface.
2. Reproduce the competition metric locally first, including clipping,
   transforms, averaging mode, and sample weights.
3. Build in order: constant baseline (format check) → fast classical baseline
   → strong baseline with out-of-fold predictions → staged experiments.
4. Save out-of-fold predictions for every model. Compare mean fold score and
   fold variance, not the best fold.
5. A public-LB move that contradicts CV is a validation defect until proven
   otherwise. Do not select on it.
6. Never train a stacker on in-sample base predictions. Never tune preprocessing
   on validation targets outside the fold boundary.

## Example

User: "My LB jumped +0.02 but CV is flat — ship it?"

1. Read `references/validation.md` leakage checklist and
   `references/submission-gates.md` acceptance criteria.
2. Verdict: not submittable on LB alone — require CV agreement or a diagnosed
   distribution-shift cause first.
