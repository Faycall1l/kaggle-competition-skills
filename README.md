# Kaggle Competition Skills

Agent skills for Kaggle competition operations via the CLI: download, push/monitor
kernels, fetch logs/output, submit and poll — plus a modeling playbook and a
learnings loop.

## Skills

| Skill | Purpose |
|---|---|
| `kaggle-cli-ops` | CLI operations: download, kernels, submit, troubleshooting, quota/auth |
| `kaggle-playbook` | Modeling judgment: validation design, endgame gates |
| `kaggle-learnings` | Memory loop: capture/recall/retrospect learnings |

## Install

Install matrix per agent (OpenCode, Claude Code, Codex, Cursor, Gemini) — see
distribution tasks. Fallback for any Agent Skills runtime:

```bash
cp -R skills/<skill-name> <your-skills-directory>/
```

## Credentials

Set `KAGGLE_API_TOKEN` (KGAT token). Never commit credentials — see `.gitignore`.
Run `doctor.py` to verify setup.
