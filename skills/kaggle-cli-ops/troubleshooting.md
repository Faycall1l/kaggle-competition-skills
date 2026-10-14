# Troubleshooting CLI Reference

Symptom → cause → corrective action for Kaggle CLI operations. Check here
before retrying any failed command — retries can consume submission slots,
quota, or restart multi-GB downloads.

## Authentication

| Symptom | Cause | Action |
|---|---|---|
| `Missing username in configuration` after `config set` | `kaggle.json` holds config values, not credentials | Re-run `kaggle auth login` or restore `username`/`key` |
| `KeyError: 'username'` from SDK auth | Same as above, surfaced one layer down | Same as above |
| 403 on private resources despite login | Anonymous fallback taken before OAuth creds | Ensure token present; prefer `KAGGLE_API_TOKEN` for scripts |
| `Permission 'kernelSessions.get' was denied` | Code-competition submit via API lacks scope | Push kernel, submit in browser (no API path) |

## Downloads

| Symptom | Cause | Action |
|---|---|---|
| `Skipping, found more recently modified local copy` | Local partial file newer than remote | Delete the partial file and re-run (resumes); `--force` only to restart from zero |
| Download dies silently at N% | Connection drop on large files | Re-run same command; never `--force` to resume |
| `404 for .../competitions/data/download/<slug>/<subpath>` | Subpath download unsupported in this release | Download the full archive, extract locally |
| Polluted `--format json` output | Pagination text printed to stdout | Parse with `--csv`, or strip non-JSON preamble lines |
| `-v` treated as version instead of CSV flag | Fixed in 2.2.x (#1082); `-v/--csv` now distinct from `--version` | Use `--format csv\|table\|json`; `-v` and `--format` are mutually exclusive |
| Bare traceback on 403/404/429/5xx | Default hides next steps (main adds hints + `--debug`) | Read the suggested next step first; re-run with `--debug` on main for the full traceback |

## CLI version skew

- Pip release 2.2.4 (23 Jul 2026, latest) lacks upstream-main flags:
  `download --unzip`, `submit --wait/--poll-interval`, `kernels push --no-run`,
  `competitions submission <ref>`, `submission-download`, unified
  `kaggle search`. `scripts/kernel_push.py` and `scripts/comp_submit.py`
  probe for flag support and degrade gracefully — do not hand-roll the flag
  without probing.

## Kernels

| Symptom | Cause | Action |
|---|---|---|
| `ModuleNotFoundError: torch_xla` on a TPU push | Pinned CPU/GPU `docker_image` overrides TPU request | Remove `docker_image` from metadata, keep `docker_image_pinning_type: latest` |
| Retired-accelerator warning on push (`NvidiaTeslaP100`, `TpuV38`, `Tpu1VmV38`, `TpuV232`, `TpuV2256`) | Shape retired platform-side; server runs a replacement (warning is main-only) | Request a current shape (`NvidiaTeslaT4`, `NvidiaTeslaA100`, `NvidiaL4`, `TpuV5E8`, `TpuV6E8`); never pin a retired shape |
| Empty `/kaggle/input` after push | Data source not attached (MCP `save_notebook` drops them) | Push via CLI with sources in metadata; push twice if first run still empty |
| Wrong files from `output <kernel>/2` | Version ignored (pre-#1201 behavior on pip ≤2.2.4) | Upgrade past 2.2.4 / use upstream main; confirm `version_label` path in installed release |
| `ValueError: too many values to unpack` on delete | Versioned ref passed to delete | `kaggle kernels delete <owner/slug>` — versions are not deletable |
| `cp932` codec crash on `kernels output` (Windows) | Non-ASCII logs on legacy console | Set UTF-8 locale or fetch logs via API |
| No `cancel` command for runaway session | Not exposed in CLI | Stop the session in the web UI |
| Kernel mounts a stale dataset version | Dataset mounts pin to the version attached when the kernel was created; later dataset versions do not reach existing kernels | Verify with a probe kernel printing the file hash; run updated code under a new kernel slug |

## Submissions

| Symptom | Cause | Action |
|---|---|---|
| `ID column submission_id not found in submission` | A per-task intermediate was uploaded instead of the merged file | Submit the merged upload file; verify header with `comp_submit.py --expect-columns` before sending |
| Submission scored 0.0 with valid format | Genuinely out-of-scope values, or blank cells rejected at scoring | Check for blank rows; confirm value ranges against the sample |
