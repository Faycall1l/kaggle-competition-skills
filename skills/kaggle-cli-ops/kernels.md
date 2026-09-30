# Kernels CLI Reference

Notebook/script lifecycle via `kaggle kernels` (alias `kaggle k`): metadata,
push, pull, output, status, logs, delete. A kernel is a hosted notebook or
script plus its versioned runs.

## Prerequisites

- Push/pull/output/status/logs/delete require credentials. See `quota-auth.md`.
- Push requires a folder with `kernel-metadata.json`; generate with
  `kaggle kernels init -p <dir>`.

## Command map

| Task | Command |
|---|---|
| List kernels | `kaggle kernels list [--user U] [--competition SLUG] [--dataset O/S]` |
| Scaffold metadata | `kaggle kernels init -p <dir>` |
| Push new version and run | `kaggle kernels push -p <dir> [-t TIMEOUT] [--accelerator A]` |
| Save version without running | `kaggle kernels push -p <dir> --no-run` (upstream main; absent from pip 2.2.4) |
| Pull source | `kaggle kernels pull <owner/slug[/v]> [-p PATH] [-w] [-m]` |
| Download output | `kaggle kernels output <owner/slug[/v]> [-p PATH] [--file-pattern RX] [--page-size N] [--page-token T]` |
| Run status | `kaggle kernels status <owner/slug[/v]>` |
| Logs | `kaggle kernels logs <owner/slug[/v]> [-f|--follow]` |
| List output files | `kaggle kernels files <owner/slug[/v]> [-v\|--format json]` |
| Delete kernel | `kaggle kernels delete <owner/slug> [-y]` |

## Version semantics

- Kernel refs accept an optional `/<version>` (`owner/slug/3`, `v3` also
  accepted). `pull`, `output`, `status`, `files`, `logs` honor it via
  `version_label`; omit it for the latest version.
- Each `push` prints `Kernel version N`; use it for submit (`-v N`).
- `delete` removes the entire kernel. Versioned refs (`owner/slug/3`) are
  rejected with guidance — individual versions cannot be deleted. The `--help`
  text still shows the `/<version>` format; ignore it for delete.

## Push behavior

- Internet defaults from metadata; code competitions require
  `enable_internet=false` or the notebook is ineligible for submission.
- The CLI sends only the `code_file` text. Sibling files in the push folder
  are NOT uploaded. Bundle helpers via a dataset source, or inline them into
  the notebook.
- Dataset mounts can lag published versions: a kernel may mount the previous
  dataset version even when the download endpoint already serves the new one.
  For code under active iteration, embed the files in a notebook bootstrap
  cell that writes them to `/kaggle/working/_bundle/` and prepends it to
  `sys.path`. The code then versions with the kernel deterministically; keep
  stable third-party code on the dataset source.
- Scripts running on Kaggle resolve their own location: a helper shipped at
  `src/task/task.py` must `sys.path.insert` its `parent.parent`, mirroring
  the v1 baseline builders. The run working directory is `/kaggle/working`
  and carries no import context.
- `sys.path` edits do not propagate to subprocesses. Notebooks that fan out to
  helper scripts must export the paths via `PYTHONPATH` in the environment,
  otherwise identically-versioned code fails with `ModuleNotFoundError` in the
  child while importing fine in the notebook.
- Data sources attach via metadata; verify mounts with
  `Path('/kaggle/input').rglob(name)` — paths vary
  (`/kaggle/input/<slug>` vs `/kaggle/input/competitions/<slug>/`).
- Accelerator: `--accelerator` (e.g. `NvidiaTeslaT4`, `TpuV5E8`). A pinned
  `docker_image` from a CPU/GPU pull overrides TPU requests — clear it when
  switching accelerator families.
- `logs -f` streams the running session (polls; set `--interval` if exposed).
  No `cancel` command exists upstream: stop runaway sessions in the web UI.

## Output behavior

- Without `--page-token`, `output` walks all pages so `--file-pattern` matches
  beyond page one. With `--page-token`, only that page downloads and the next
  token prints.
- Non-ASCII logs can crash Windows `cp932` consoles; prefer the API or UTF-8
  locale (see `troubleshooting.md`).

## Submitting kernel output

- `/kaggle/working` holds intermediates alongside the final file. Submit only
  the merged upload file (e.g. `submission.csv`); per-task intermediates are
  keyed differently and the leaderboard rejects them
  (`ID column submission_id not found`).
- Verify before submit: header matches the competition template exactly and no
  row is blank. `comp_submit.py --expect-columns` enforces this without
  loading the file.
- End every submission-producing notebook with a cell that prints the exact
  submit target path, its header, and its row count.
