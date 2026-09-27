# Experiment Ledger Reference

One ledger per competition workspace: every attempt recorded with its method,
kernel version, and score. The ledger is the active directory of tries — read
it before planning the next attempt, write to it after every run.

## Commands

| Task | Command |
|---|---|
| Record an attempt | `scripts/exp.py --ledger <path> add --competition <slug> --method <name> --kernel <ref> --version <N> --detail <notes>` |
| Attach a result | `scripts/exp.py --ledger <path> score <id> --score <X> --status <state> --submission <ref>` |
| Review tries | `scripts/exp.py --ledger <path> list [--competition <slug>]` |

## Rules

- Log the attempt BEFORE pushing the kernel (method, config). Log the result
  when the run terminates, whatever the outcome — errors are tries too.
- Method names are short slugs (`task1-neighbors`, `queue-shockwave`);
  distinguishing detail goes in `--detail`, not the name.
- Never edit or delete entries. Superseded attempts stay visible; that is the
  point of an append-only log.
- One ledger file per competition, stored in the workspace root next to the
  kernels (e.g. `competitions/<slug>/.runs.jsonl`).

## Long runs

Kernels outlive wrapper invocations. For runs longer than the local timeout:

1. Push with `kernel_push.py --dir <dir> --no-wait` — returns immediately
   with the version number.
2. Reattach later with `kernel_push.py --resume <owner/slug> --version <N>
   [--title <title>] [--output-dir <dir>]` — polls to terminal state and
   optionally downloads output on completion.
3. Record both steps in the ledger: the attempt at push time, the result at
   termination.
