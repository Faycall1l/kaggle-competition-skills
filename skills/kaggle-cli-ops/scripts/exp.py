"""Run ledger: append-only record of competition attempts.

Each competition keeps an active directory of tries: what method ran, on which
kernel version, what it scored. Events are JSON lines; `list` joins attempts
with their latest results. Stdlib only.

Ledger location is explicit (--ledger); keep one per competition workspace.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import UsageError, emit, run


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Append-only record of competition attempts.")
    parser.add_argument("--ledger", default=".runs.jsonl", help="Ledger file (default: .runs.jsonl).")
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add", help="Record a new attempt.")
    add.add_argument("--competition", required=True)
    add.add_argument("--method", required=True, help="What ran, e.g. task1-neighbors.")
    add.add_argument("--kernel", default=None, help="Kernel ref that ran.")
    add.add_argument("--version", type=int, default=None, help="Kernel version that ran.")
    add.add_argument("--detail", default="", help="Config notes (hyperparameters, splits).")
    score = sub.add_parser("score", help="Attach a result to an attempt.")
    score.add_argument("id", type=int)
    score.add_argument("--score", type=float, required=True)
    score.add_argument("--status", default="complete")
    score.add_argument("--submission", default=None, help="Submission ref.")
    lst = sub.add_parser("list", help="List attempts with latest results.")
    lst.add_argument("--competition", default=None)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    ledger = Path(args.ledger)
    if args.command == "add":
        emit(add_attempt(ledger, args.competition, args.method, args.kernel, args.version, args.detail))
    elif args.command == "score":
        emit(attach_result(ledger, args.id, args.score, args.status, args.submission))
    else:
        emit({"ok": True, "runs": list_runs(ledger, args.competition)})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read(ledger: Path) -> list[dict]:
    if not ledger.is_file():
        return []
    events = []
    for line in ledger.read_text().splitlines():
        line = line.strip()
        if line:
            events.append(json.loads(line))
    return events


def add_attempt(
    ledger: Path, competition: str, method: str, kernel: str | None, version: int | None, detail: str
) -> dict:
    """Append an attempt event. Returns its id."""
    if not competition.strip() or not method.strip():
        raise UsageError("competition and method must be non-empty")
    events = _read(ledger)
    run_id = max([e.get("id", 0) for e in events if e.get("type") == "attempt"], default=0) + 1
    event = {
        "type": "attempt",
        "id": run_id,
        "at": _now(),
        "competition": competition,
        "method": method,
        "kernel": kernel,
        "version": version,
        "detail": detail,
    }
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a") as handle:
        handle.write(json.dumps(event) + "\n")
    return {"ok": True, **event}


def attach_result(ledger: Path, run_id: int, score: float, status: str, submission: str | None) -> dict:
    """Append a result event linked to an attempt id."""
    events = _read(ledger)
    if not any(e.get("type") == "attempt" and e.get("id") == run_id for e in events):
        raise UsageError(f"no attempt with id {run_id}")
    event = {"type": "result", "id": run_id, "at": _now(), "score": score, "status": status, "submission": submission}
    with ledger.open("a") as handle:
        handle.write(json.dumps(event) + "\n")
    return {"ok": True, **event}


def list_runs(ledger: Path, competition: str | None) -> list[dict]:
    """Attempts joined with their latest result, newest first."""
    attempts: dict[int, dict] = {}
    for event in _read(ledger):
        if event.get("type") == "attempt":
            if competition is None or event.get("competition") == competition:
                attempts[event["id"]] = dict(event)
        elif event.get("type") == "result" and event.get("id") in attempts:
            attempts[event["id"]]["score"] = event.get("score")
            attempts[event["id"]]["status"] = event.get("status")
            attempts[event["id"]]["submission"] = event.get("submission")
    return sorted(attempts.values(), key=lambda r: r["id"], reverse=True)


if __name__ == "__main__":
    run(main)
