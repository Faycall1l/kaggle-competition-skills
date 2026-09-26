# Kaggle Competition Skills

Agent skills for Kaggle competition operations via the CLI: download, push/monitor
kernels, fetch logs/output, submit and poll — plus a modeling playbook and a
learnings memory loop.

## Skills

| Skill | Purpose |
|---|---|
| `kaggle-cli-ops` | CLI operations: download, kernels, submit, troubleshooting, quota/auth |
| `kaggle-playbook` | Modeling judgment: validation design, submission acceptance criteria |
| `kaggle-learnings` | Memory loop: capture/recall/archive learnings |

## Install

| Agent | Command |
|---|---|
| Claude Code | `/plugin marketplace add Faycall1l/kaggle-competition-skills` then `/plugin install kaggle-competition-skills` |
| Codex | `codex plugin marketplace add Faycall1l/kaggle-competition-skills` |
| OpenCode / Cursor / Gemini / Windsurf | `npx skills add Faycall1l/kaggle-competition-skills` |
| Any Agent Skills runtime | `cp -R skills/<skill-name> <your-skills-directory>/` |

## Prompts

Competition setup (any agent):

```text
Set up the titanic competition with kaggle-cli-ops: run doctor.py, download
data with comp_init.py, and report workspace paths.
```

Push and monitor:

```text
Push ./my-kernel with kernel_push.py, monitor to a terminal state, and fetch
logs on failure.
```

Pre-submit verification:

```text
Verify this submission against kaggle-playbook acceptance criteria, then run
comp_submit.py preflight for <slug>.
```

## Credentials

Set `KAGGLE_API_TOKEN` (KGAT token from `kaggle.com/settings`). Never commit
credentials — see `.gitignore`. Run `doctor.py` to verify setup.

## Layout

```
skills/kaggle-cli-ops/     # router + references + scripts
skills/kaggle-playbook/    # methodology router + references
skills/kaggle-learnings/   # memory router + kln.py
tests/                     # offline mocked suite (pytest)
evals/titanic_e2e/         # live transcripts (credential-gated)
examples/                  # tabular-baseline, code-competition
```
