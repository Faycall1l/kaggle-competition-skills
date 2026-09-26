"""Shared helpers for kaggle-cli-ops scripts.

Contract: JSON to stdout, diagnostics to stderr. Exit codes: 0 ok,
2 usage error, 3 blocked (external action required, see `next_action`).
Stdlib only.
"""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Any, NoReturn


class BlockedError(Exception):
    """Operation cannot proceed without external action (auth, rules, quota)."""

    def __init__(self, message: str, next_action: str) -> None:
        super().__init__(message)
        self.next_action = next_action


class UsageError(Exception):
    """Invalid arguments supplied by the caller."""


def emit(data: dict[str, Any]) -> None:
    """Write a JSON document to stdout."""
    sys.stdout.write(json.dumps(data) + "\n")


def log(message: str) -> None:
    """Write a diagnostic line to stderr."""
    sys.stderr.write(message + "\n")


def fail(message: str, code: int = 2, next_action: str | None = None) -> NoReturn:
    """Emit an error document and exit with the given code."""
    doc: dict[str, Any] = {"ok": False, "error": message}
    if next_action is not None:
        doc["next_action"] = next_action
    emit(doc)
    raise SystemExit(code)


def run(main: Any) -> None:
    """Entry-point wrapper mapping exceptions to exit codes."""
    try:
        main()
    except UsageError as exc:
        fail(str(exc), code=2)
    except BlockedError as exc:
        fail(str(exc), code=3, next_action=exc.next_action)


def parse_kernel_ref(ref: str) -> tuple[str, str, str | None]:
    """Split `owner/slug[/version]`; raise UsageError on malformed input."""
    parts = ref.strip().rstrip("/").split("/")
    if len(parts) == 2 and all(parts):
        return parts[0], parts[1], None
    if len(parts) == 3 and all(parts):
        return parts[0], parts[1], parts[2]
    raise UsageError(f"Invalid kernel ref {ref!r}; expected owner/slug[/version]")


def parse_dataset_ref(ref: str) -> tuple[str | None, str, str | None]:
    """Split `[owner/]slug[/version]`; owner may be omitted (uses configured user)."""
    parts = ref.strip().rstrip("/").split("/")
    if len(parts) == 1 and parts[0]:
        return None, parts[0], None
    if len(parts) == 2 and all(parts):
        return parts[0], parts[1], None
    if len(parts) == 3 and all(parts):
        return parts[0], parts[1], parts[2]
    raise UsageError(f"Invalid dataset ref {ref!r}; expected [owner/]slug[/version]")


def backoff_delays(max_attempts: int, base: float = 5.0, cap: float = 300.0) -> list[float]:
    """Polling delays with linear backoff: base, 2*base, ... capped."""
    if max_attempts < 1:
        raise UsageError("max_attempts must be >= 1")
    delays: list[float] = []
    delay = base
    for _ in range(max_attempts - 1):
        delays.append(min(delay, cap))
        delay *= 2
    return delays


def run_cli(args: list[str], timeout: int = 300, binary: str = "kaggle") -> tuple[int, str, str]:
    """Run the kaggle CLI, capturing output. Never logs secret values."""
    try:
        proc = subprocess.run([binary, *args], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, "", str(exc)
    return proc.returncode, proc.stdout, proc.stderr


def extract_json(text: str) -> Any:
    """Parse JSON from CLI output, skipping non-JSON preamble lines on stdout.

    The CLI prints warnings (e.g. key-permission notices) to stdout ahead of
    `--format json` payloads. Raises ValueError when no JSON value is found.
    """
    decoder = json.JSONDecoder()
    for i, line in enumerate(text.splitlines()):
        stripped = line.strip()
        if stripped[:1] in ("{", "["):
            try:
                value, _ = decoder.raw_decode("\n".join(text.splitlines()[i:]))
                return value
            except ValueError:
                continue
    raise ValueError("no JSON value in output")
