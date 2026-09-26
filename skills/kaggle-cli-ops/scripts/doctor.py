"""Preflight check for Kaggle CLI operations.

Inspects credential sources, CLI version, and (optionally) quota, then emits
a JSON verdict to stdout. Never prints secret values.
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import emit, extract_json, run, run_cli

KAGGLE_DIR_NAME = ".kaggle"
API_TOKEN_ENV = "KAGGLE_API_TOKEN"
LEGACY_USER_ENV = "KAGGLE_USERNAME"
LEGACY_KEY_ENV = "KAGGLE_KEY"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Preflight check for Kaggle CLI operations.")
    parser.add_argument("--check-quota", action="store_true", help="Include quota lookup (requires credentials).")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    verdict = check(include_quota=args.check_quota)
    emit(verdict)


def kaggle_dir(home: Path | None = None) -> Path:
    """Resolve the Kaggle config directory without side effects."""
    return (home or Path.home()) / KAGGLE_DIR_NAME


def detect_credentials(env: dict[str, str], home: Path) -> tuple[list[dict], int | None]:
    """Report credential sources present. Values are never included.

    Distinguishes a `kaggle.json` holding API credentials from one holding
    only `config set` values (the #1009 failure mode).
    """
    sources: list[dict] = []
    kdir = kaggle_dir(home)

    if env.get(API_TOKEN_ENV):
        sources.append({"source": "env:KAGGLE_API_TOKEN", "present": True})

    token_file = kdir / "access_token"
    if token_file.is_file():
        sources.append({"source": "file:access_token", "present": True})

    if env.get(LEGACY_USER_ENV) and env.get(LEGACY_KEY_ENV):
        sources.append({"source": "env:KAGGLE_USERNAME/KAGGLE_KEY", "present": True})

    kaggle_json = kdir / "kaggle.json"
    if kaggle_json.is_file():
        try:
            keys = set(json.loads(kaggle_json.read_text()).keys())
        except (OSError, ValueError):
            keys = set()
        if {"username", "key"} <= keys:
            sources.append({"source": "file:kaggle.json", "present": True, "has_credentials": True})
        else:
            sources.append(
                {
                    "source": "file:kaggle.json",
                    "present": True,
                    "has_credentials": False,
                    "note": "config values only; re-run `kaggle auth login`",
                }
            )

    try:
        mode = stat.S_IMODE(kaggle_json.stat().st_mode) if kaggle_json.is_file() else None
    except OSError:
        mode = None
    return sources, mode


def check_cli_version() -> dict:
    """Report installed CLI version; warn when older than the floor we test against."""
    code, out, err = run_cli(["--version"])
    if code != 0:
        return {"name": "cli", "status": "error", "detail": (err or out).strip()[-200:]}
    lines = [line for line in out.strip().splitlines() if line.startswith("Kaggle")]
    version = lines[0] if lines else out.strip().splitlines()[0] if out.strip() else "unknown"
    return {"name": "cli", "status": "ok", "version": version}


def check_quota() -> dict:
    """Fetch accelerator quota as JSON. Requires credentials; caller gates on them."""
    code, out, err = run_cli(["quota", "--format", "json"])
    if code != 0:
        return {"name": "quota", "status": "error", "detail": (err or out).strip()[-200:]}
    try:
        return {"name": "quota", "status": "ok", "quota": extract_json(out)}
    except ValueError:
        return {"name": "quota", "status": "error", "detail": "non-JSON quota output"}


def check(include_quota: bool = False) -> dict:
    """Collect environment facts; pure logic kept separate for testing."""
    home = Path.home()
    sources, kaggle_json_mode = detect_credentials(dict(os.environ), home)
    checks: list[dict] = [{"name": "credentials", "sources": sources}]
    checks.append(check_cli_version())
    if kaggle_json_mode is not None and kaggle_json_mode != 0o600:
        checks.append({"name": "kaggle.json permissions", "status": "warn", "mode": oct(kaggle_json_mode)})
    ok = any(s.get("present") for s in sources)
    if include_quota:
        if not ok:
            checks.append({"name": "quota", "status": "skip", "detail": "no credentials"})
        else:
            checks.append(check_quota())
    verdict: dict = {"ok": ok, "include_quota": include_quota, "checks": checks}
    if not ok:
        verdict["next_action"] = "set KAGGLE_API_TOKEN or run `kaggle auth login`"
    return verdict


if __name__ == "__main__":
    run(main)
