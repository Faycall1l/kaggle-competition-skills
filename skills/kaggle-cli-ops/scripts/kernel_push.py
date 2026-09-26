"""Push a kernel, monitor its run, fetch logs and output.

Wraps `kaggle kernels push/status/logs/output` with polling backoff and
agent-safe JSON output. Emits JSON to stdout; diagnostics to stderr.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import BlockedError, UsageError, backoff_delays, emit, log, run, run_cli

TERMINAL_STATES = ("COMPLETE", "ERROR", "CANCELLED")
VERSION_RE = re.compile(r"Kernel version (\d+)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Push a kernel, monitor its run, fetch logs and output.")
    parser.add_argument("--dir", required=True, help="Kernel folder containing kernel-metadata.json.")
    parser.add_argument("--timeout", type=int, default=None, help="Limit kernel run time in seconds.")
    parser.add_argument("--accelerator", default=None, help="Accelerator, e.g. NvidiaTeslaT4.")
    parser.add_argument("--no-run", action="store_true", help="Save version without running (upstream main only).")
    parser.add_argument("--no-wait", action="store_true", help="Return after push without monitoring.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    emit(push(args.dir, timeout=args.timeout, accelerator=args.accelerator, no_run=args.no_run, wait=not args.no_wait))


def push(kernel_dir: str, timeout: int | None, accelerator: str | None, no_run: bool, wait: bool) -> dict:
    """Push and optionally monitor; steps monkeypatchable for testing."""
    slug = read_kernel_slug(Path(kernel_dir))
    version = push_version(Path(kernel_dir), timeout=timeout, accelerator=accelerator, no_run=no_run)
    result: dict = {"ok": True, "kernel": slug, "version": version}
    if wait and not no_run:
        result["status"] = poll_status(slug, version)
    return result


def read_kernel_slug(kernel_dir: Path) -> str:
    """Read the kernel slug from metadata, rejecting versioned identifiers."""
    meta = kernel_dir / "kernel-metadata.json"
    if not meta.is_file():
        raise UsageError(f"no kernel-metadata.json in {kernel_dir} (run `kaggle kernels init`)")
    try:
        ref = json.loads(meta.read_text())["id"]
    except (OSError, ValueError, KeyError) as exc:
        raise UsageError(f"unreadable kernel-metadata.json: {exc}")
    parts = ref.strip().rstrip("/").split("/")
    if len(parts) != 2 or not all(parts):
        raise UsageError(f"metadata id {ref!r} must be owner/slug without version")
    return ref.strip()


def push_version(kernel_dir: Path, timeout: int | None, accelerator: str | None, no_run: bool) -> int:
    """Run the CLI push and return the new version number."""
    cmd = ["kernels", "push", "-p", str(kernel_dir)]
    if timeout is not None:
        cmd += ["--timeout", str(timeout)]
    if accelerator:
        cmd += ["--accelerator", accelerator]
    if no_run:
        cmd += ["--no-run"]
    code, out, err = run_cli(cmd, timeout=600)
    if code != 0:
        raise BlockedError(f"push failed: {(err or out).strip()[-300:]}", "inspect metadata and quota, then retry")
    match = VERSION_RE.search(out)
    if not match:
        raise BlockedError(f"push output missing version: {out.strip()[-200:]}", "check `kaggle kernels status`")
    return int(match.group(1))


def parse_status(text: str) -> str:
    """Extract the run state from `kernels status` output."""
    upper = text.upper()
    for state in TERMINAL_STATES + ("RUNNING", "QUEUED"):
        if state in upper:
            return state
    raise BlockedError(f"unrecognized status output: {text.strip()[-200:]}", "check `kaggle kernels status` manually")


def poll_status(slug: str, version: int, max_attempts: int = 24) -> dict:
    """Poll until a terminal state; fetch logs on failure."""
    ref = f"{slug}/{version}"
    for delay in backoff_delays(max_attempts):
        code, out, err = run_cli(["kernels", "status", ref], timeout=120)
        if code != 0:
            raise BlockedError(f"status failed: {(err or out).strip()[-200:]}", "check credentials and kernel ref")
        state = parse_status(out)
        log(f"status {ref}: {state}")
        if state in TERMINAL_STATES:
            result = {"state": state}
            if state != "COMPLETE":
                result["logs_tail"] = fetch_logs(slug, version)
            return result
        time.sleep(delay)
    code, out, err = run_cli(["kernels", "status", ref], timeout=120)
    return {"state": parse_status(out) if code == 0 else "TIMEOUT"}


def fetch_logs(slug: str, version: int, dest: Path | None = None) -> str:
    """Fetch logs; optionally write to dest. Returns tail for the verdict."""
    code, out, err = run_cli(["kernels", "logs", f"{slug}/{version}"], timeout=300)
    if code != 0:
        return (err or out).strip()[-2000:]
    if dest is not None:
        dest.write_text(out)
    lines = out.strip().splitlines()
    return "\n".join(lines[-50:])


def download_output(slug: str, version: int, dest: Path, file_pattern: str | None = None) -> dict:
    """Download kernel output files. Returns paths written."""
    cmd = ["kernels", "output", f"{slug}/{version}", "-p", str(dest)]
    if file_pattern:
        cmd += ["--file-pattern", file_pattern]
    code, out, err = run_cli(cmd, timeout=1800)
    if code != 0:
        raise BlockedError(f"output download failed: {(err or out).strip()[-300:]}", "check run state first")
    paths = sorted(p.name for p in dest.iterdir()) if dest.is_dir() else []
    return {"dir": str(dest), "files": paths}


if __name__ == "__main__":
    run(main)
