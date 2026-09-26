"""Submit predictions to a competition with preflight verification.

Wraps `kaggle competitions submit` with submission-limits preflight, metadata
format validation, and polling. Code-competition 403s degrade to an explicit
browser-submit instruction. Emits JSON to stdout; diagnostics to stderr.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import BlockedError, UsageError, backoff_delays, emit, extract_json, log, parse_kernel_ref, run, run_cli


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Submit predictions with preflight verification.")
    parser.add_argument("competition", help="Competition slug.")
    parser.add_argument("--file", required=True, help="Submission file, or kernel output name for code competitions.")
    parser.add_argument("--message", required=True, help="Submission description.")
    parser.add_argument("--kernel", default=None, help="Kernel ref for code competitions (owner/slug).")
    parser.add_argument("--version", default=None, help="Kernel version for code competitions.")
    parser.add_argument("--wait", action="store_true", help="Poll until scored (CLI releases with --wait only).")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    emit(
        submit(
            args.competition,
            file=args.file,
            message=args.message,
            kernel=args.kernel,
            version=args.version,
            wait=args.wait,
        )
    )


def submit(competition: str, file: str, message: str, kernel: str | None, version: str | None, wait: bool) -> dict:
    """Submit and optionally poll; steps monkeypatchable for testing."""
    if not competition or "/" in competition:
        raise UsageError(f"Invalid competition slug {competition!r}")
    if kernel and not version:
        raise UsageError("code-competition submit requires --version with --kernel")
    preflight(competition, file, kernel)
    ref = send(competition, file, message, kernel, version)
    result: dict = {"ok": True, "competition": competition, "ref": ref}
    if wait:
        result["score"] = poll(competition, ref)
    return result


def preflight(competition: str, file: str, kernel: str | None) -> None:
    """Verify allowance, file presence, and header compatibility. Raises on blockers."""
    check_allowance(competition)
    if kernel:
        check_kernel_submittable(kernel)
    else:
        check_file(file, competition)


def check_allowance(competition: str) -> None:
    """Fail when no daily submissions remain."""
    code, out, err = run_cli(["competitions", "submission-limits", competition, "--json"], timeout=120)
    if code != 0:
        raise BlockedError(f"allowance check failed: {(err or out).strip()[-200:]}", "verify competition access")
    try:
        remaining = extract_json(out).get("numAllowedNow")
    except ValueError:
        return
    if isinstance(remaining, int) and remaining <= 0:
        raise BlockedError("no daily submissions remaining", "wait for reset or request quota")


def check_file(file: str, competition: str) -> None:
    """Verify the submission file exists and matches the sample header when available."""
    path = Path(file)
    if not path.is_file():
        raise UsageError(f"submission file not found: {file}")
    sample = Path(competition) / "data" / "sample_submission.csv"
    if sample.is_file():
        expected = sample.read_text().splitlines()[0].split(",")
        actual = path.read_text().splitlines()[0].split(",")
        if expected != actual:
            raise BlockedError(
                f"header mismatch: expected {expected}, got {actual}", "regenerate from sample_submission.csv"
            )


def check_kernel_submittable(kernel: str) -> None:
    """Reject kernels that cannot score: versioned refs or internet-enabled metadata."""
    _owner, slug, ver = parse_kernel_ref(kernel)
    if ver:
        raise UsageError(f"kernel ref {kernel!r} must be owner/slug; pass --version separately")
    meta_candidates = [Path("kernels") / slug / "kernel-metadata.json", Path(slug) / "kernel-metadata.json"]
    for meta in meta_candidates:
        if meta.is_file():
            try:
                if json.loads(meta.read_text()).get("enable_internet"):
                    raise BlockedError(
                        "kernel has internet enabled; code competitions require it off",
                        "set enable_internet=false and re-push",
                    )
            except (OSError, ValueError):
                pass


def send(competition: str, file: str, message: str, kernel: str | None, version: str | None) -> str:
    """Run the CLI submit. Returns the submission ref.

    Upstream main prints `Submission ref: <ref>`; pip releases (e.g. 2.2.4) do
    not. Fall back to matching the unique description message in the
    submissions list. Never returns unparseable output as a ref.
    """
    cmd = ["competitions", "submit", competition, "-f", file, "-m", message]
    if kernel:
        cmd += ["-k", kernel, "-v", str(version)]
    code, out, err = run_cli(cmd, timeout=600)
    combined = (out + err).strip()
    if code != 0:
        if "403" in combined or "kernelSessions.get" in combined:
            raise BlockedError(
                "code-competition submit rejected by API (missing kernelSessions.get scope)",
                "push the kernel, then submit in the browser",
            )
        raise BlockedError(f"submit failed: {combined[-300:]}", "inspect the message and retry")
    for line in combined.splitlines():
        if "Submission ref:" in line:
            ref = line.split("Submission ref:")[-1].strip()
            if ref:
                return ref
    log("CLI did not print a submission ref; matching by description message")
    return ref_by_description(competition, message)


def ref_by_description(competition: str, message: str) -> str:
    """Find the newest submission row with an exact description match."""
    code, out, err = run_cli(["competitions", "submissions", "-c", competition, "--format", "json"], timeout=120)
    if code != 0:
        raise BlockedError(f"submissions lookup failed: {(err or out).strip()[-200:]}", "verify competition access")
    try:
        rows = extract_json(out)
    except ValueError:
        raise BlockedError("submissions lookup returned non-JSON", "retry the lookup")
    if not isinstance(rows, list):
        raise BlockedError("submissions lookup returned unexpected shape", "retry the lookup")
    matches = [r for r in rows if str(r.get("description", "")) == message and r.get("ref") is not None]
    if not matches:
        raise BlockedError("submitted row not visible yet", "wait and retry `submissions -c <slug>`")
    matches.sort(key=lambda r: (str(r.get("date", "")), str(r.get("ref", ""))))
    return str(matches[-1]["ref"])


def poll(competition: str, ref: str, max_attempts: int = 24) -> dict:
    """Poll submissions until the ref reaches a terminal state."""
    for delay in backoff_delays(max_attempts):
        state = submission_state(competition, ref)
        log(f"submission {ref}: {state}")
        if state in ("complete", "error"):
            return {"state": state}
        time.sleep(delay)
    return {"state": submission_state(competition, ref)}


def normalize_status(raw: str) -> str:
    """Normalize backend enum names (`SubmissionStatus.COMPLETE`) to plain states (`complete`)."""
    return raw.lower().removeprefix("submissionstatus.")


def submission_state(competition: str, ref: str) -> str:
    """Read the current state of one submission from the submissions list."""
    code, out, err = run_cli(["competitions", "submissions", "-c", competition, "--format", "json"], timeout=120)
    if code != 0:
        combined = (err or out).strip()
        if "400" in combined and "ListSubmissions" in combined:
            return "unknown"
        raise BlockedError(f"submissions lookup failed: {combined[-200:]}", "verify competition access")
    try:
        rows = extract_json(out)
    except ValueError:
        return "unknown"
    for row in rows if isinstance(rows, list) else []:
        if str(row.get("ref", "")) == ref or str(row.get("fileName", "")) == ref:
            return normalize_status(str(row.get("status", "unknown")))
    return "unknown"


def leaderboard(competition: str, top: int = 10) -> list[dict]:
    """Fetch the public leaderboard head for gap analysis."""
    code, out, err = run_cli(["competitions", "leaderboard", competition, "--format", "json"], timeout=120)
    if code != 0:
        raise BlockedError(f"leaderboard failed: {(err or out).strip()[-200:]}", "verify competition access")
    try:
        rows = json.loads(out)
    except ValueError:
        return []
    return rows[:top] if isinstance(rows, list) else []


if __name__ == "__main__":
    run(main)
