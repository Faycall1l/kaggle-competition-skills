---
name: kaggle-cli-ops
description: "Kaggle CLI competition operations: download data, push/monitor kernels, fetch logs/output, submit and poll. Use when the user mentions Kaggle CLI commands, kaggle competitions/kernels workflows, notebook push/submit/poll, or a kaggle.com/c/... URL tied to CLI execution."
license: MIT
compatibility: "Python 3.11+, kaggle>=2.2.3; KAGGLE_API_TOKEN required for writes"
metadata: {"author": "Faycall1l", "version": "0.1.0"}
---

# Kaggle CLI Ops

## When to activate

- User mentions Kaggle CLI commands, flags, or `kaggle` error output.
- User shares a `kaggle.com/c/...` competition URL and wants CLI execution.
- User asks to download competition data, push/monitor a notebook, fetch logs/output, or submit/poll.
- User asks about quota, auth, or kernel troubleshooting tied to the CLI.

## When NOT to use

- Generic ML questions with no Kaggle tie-in (modeling advice belongs to `kaggle-playbook`).
- Badge collection, benchmarks, or forum writeups without a CLI operation.
- MCP-only workflows — this skill drives the `kaggle` CLI, not the MCP server.

## Workflow catalog

Read only the reference required for the current task. Run scripts from this
skill directory.

| Task | Reference | Script |
|---|---|---|
| Download competition data, scaffold workspace | `competition.md` | `scripts/comp_init.py <slug>` |
| Push/monitor notebook, fetch logs and output | `kernels.md` | `scripts/kernel_push.py` |
| Submit predictions, poll status, check leaderboard | `competition.md` | `scripts/comp_submit.py` |
| Auth, quota, environment preflight | `quota-auth.md` | `scripts/doctor.py` |
| Failure diagnosis (mounts, 403s, JSON, encoding) | `troubleshooting.md` | — |

## Instructions

1. Run `scripts/doctor.py` first on any write path (push, submit, upload). Abort
   and report `next_action` if credentials, quota, or rules acceptance block.
2. Prefer `kaggle <group> --help` over memory when a flag is uncertain.
3. Never submit, publish, or upload without explicit user confirmation. State the
   resource, visibility, and quota/submission-slot cost before running.
4. Scripts print JSON to stdout and diagnostics to stderr. Parse stdout only.
5. Competition data mounts vary (`/kaggle/input/<slug>` vs
   `/kaggle/input/competitions/<slug>/`). Generated code must locate inputs with
   `Path('/kaggle/input').rglob(name)`, never a hardcoded path.
6. Code competitions require `enable_internet=false` and browser submit as
   fallback when the API returns 403. See `troubleshooting.md`.

## Example

User: "Download titanic and set up a workspace."

1. `python scripts/doctor.py` → credentials valid.
2. `python scripts/comp_init.py titanic` → workspace JSON with data paths.
3. Report paths and next step (baseline), no further action.
