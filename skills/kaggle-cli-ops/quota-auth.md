# Quota and Authentication Reference

Credential selection, quota preflight, and config handling for CLI-driven
Kaggle work. Run `scripts/doctor.py` before any write path.

## Credential sources (precedence)

1. Access token (`KAGGLE_API_TOKEN` env or `~/.kaggle/access_token`).
2. Legacy API key (`KAGGLE_USERNAME`/`KAGGLE_KEY` env or `~/.kaggle/kaggle.json`
   with `username`/`key`).
3. OAuth credentials from `kaggle auth login` (browser flow).
4. Anonymous access, for commands that support it (public reads only).

Rules:

- Scripts must use source 1. Never print, log, or echo token values.
- `~/.kaggle/kaggle.json` must have mode `600`.
- `kaggle config set` writes non-credential values into `kaggle.json`; a file
  containing only config values (no `username`/`key`) breaks legacy auth.
  Re-run `kaggle auth login` if that occurs.
- Token for scripts: generate at `kaggle.com/settings`, single `KGAT_…` line.

## Auth commands

| Task | Command |
|---|---|
| Browser login (OAuth) | `kaggle auth login` |
| Print active access token | `kaggle auth print-access-token` |
| Revoke refresh token | `kaggle auth revoke` |
| View config | `kaggle config view` |
| Set default competition | `kaggle config set -n competition -v <slug>` |

## Quota preflight

- `kaggle quota [--format json]` shows weekly GPU/TPU allowance. Check before
  every push; a push without quota queues or fails remotely.
- `kaggle competitions submission-limits <slug> [--json]` shows remaining
  daily submissions. Check before every submit.
- State both costs to the user and require explicit confirmation before
  consuming quota or slots.
