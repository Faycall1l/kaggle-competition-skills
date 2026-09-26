# Competitions CLI Reference

Discovery, download, submission, and leaderboard inspection via
`kaggle competitions` (alias `kaggle c`).

## Prerequisites

- Rules accepted on `kaggle.com/c/<slug>` before download or submit. API calls
  fail without it; surface the rules URL, not the raw 403.
- Credentials: `KAGGLE_API_TOKEN`, OAuth (`kaggle auth login`), or legacy
  `~/.kaggle/kaggle.json`. See `quota-auth.md`.

## Command map

| Task | Command |
|---|---|
| List competitions | `kaggle competitions list [--group entered] [--category featured] [--sort-by latestDeadline]` |
| List competition files | `kaggle competitions files -c <slug> [-v|--csv] [--page-size N]` |
| Download all files | `kaggle competitions download -c <slug> [-p PATH] [--force] [--unzip]` |
| Download one file | `kaggle competitions download -c <slug> -f <file> [-p PATH]` |
| Submit predictions | `kaggle competitions submit <slug> -f <file> -m <message>` |
| Submit from kernel output (code competitions) | `kaggle competitions submit <slug> -k <owner/slug> -v <N> -f <output> -m <message>` |
| Wait for score | append `--wait [SECONDS] [--poll-interval N]` |
| List submissions | `kaggle competitions submissions -c <slug> [-v|--csv]` |
| Remaining submission allowance | `kaggle competitions submission-limits <slug> [--json]` |
| Leaderboard | `kaggle competitions leaderboard <slug> [-s|--show] [-d|--download]` |

Flag availability varies by release; confirm with `--help` on the installed
version. `--unzip` (download) and `--wait`/`--poll-interval` (submit) exist on
upstream main but are absent from pip release 2.2.4.

## Download behavior

- Output is `<slug>.zip`; with `--unzip` it is extracted (fallback on older
  releases: `unzip <slug>.zip` manually).
- Resume: re-run the same command; a partial file resumes. `--force` restarts
  from zero — never use it to resume (see `troubleshooting.md`).
- `Skipping, found more recently modified local copy` means the local file is
  newer than the remote; delete it or pass `--force` only to restart cleanly.

## Submission behavior

- File competitions: `-f` is a local path. Code competitions: `-f` is the
  output filename produced by kernel version `-v` of `-k <owner/slug>`.
- On success the CLI prints `Submission ref:`; poll status with
  `kaggle competitions submissions -c <slug>`.
- `--wait` blocks until scored (default cap 12h, bounded by notebook runtime)
  and exits non-zero on scoring failure or timeout. `--poll-interval` minimum
  5s. On releases without `--wait`, poll with `submissions` instead.
- Check `submission-limits` before every submit; each attempt can consume a
  daily slot.
- Code-competition API submit may return 403 (`kernelSessions.get` scope).
  Fallback: push the kernel, then submit in the browser. Never retry-submit
  blindly — each attempt can consume a daily submission slot.
- `--sandbox` is for hosts/admins only.

## Workspace layout (via `scripts/comp_init.py`)

```
<slug>/
├── data/            # downloaded + extracted competition files
├── submissions/     # timestamped submission archives + LOG.md
└── README.md        # metric, deadline, rules URL
```
