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

## Kernels

| Symptom | Cause | Action |
|---|---|---|
| `ModuleNotFoundError: torch_xla` on a TPU push | Pinned CPU/GPU `docker_image` overrides TPU request | Remove `docker_image` from metadata, keep `docker_image_pinning_type: latest` |
| Empty `/kaggle/input` after push | Data source not attached (MCP `save_notebook` drops them) | Push via CLI with sources in metadata; push twice if first run still empty |
| Wrong files from `output <kernel>/2` | Version ignored (pre-#1201 behavior) | Upgrade CLI; confirm `version_label` path in installed release |
| `ValueError: too many values to unpack` on delete | Versioned ref passed to delete | `kaggle kernels delete <owner/slug>` — versions are not deletable |
| `cp932` codec crash on `kernels output` (Windows) | Non-ASCII logs on legacy console | Set UTF-8 locale or fetch logs via API |
| No `cancel` command for runaway session | Not exposed in CLI | Stop the session in the web UI |
