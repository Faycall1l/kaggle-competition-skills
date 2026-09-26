"""CLI for the kaggle-learnings file memory.

Stores one markdown file per learning under a root directory (default
`.learnings/` in the cwd). Emits JSON to stdout; diagnostics to stderr.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage file-based learnings.")
    parser.add_argument("--root", default=".learnings", help="Learnings directory (default: .learnings).")
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add", help="Store a new learning.")
    add.add_argument("--title", required=True)
    add.add_argument("--finding", required=True)
    add.add_argument("--competition", default="general")
    add.add_argument("--evidence", default="")
    lst = sub.add_parser("list", help="List learnings, optionally filtered.")
    lst.add_argument("--competition", default=None)
    lst.add_argument("--query", default=None)
    arch = sub.add_parser("archive", help="Archive a learning by id (never delete).")
    arch.add_argument("id", type=int)
    arch.add_argument("--reason", required=True)
    return parser


def main() -> None:
    import json

    args = build_parser().parse_args()
    root = Path(args.root)
    if args.command == "add":
        result = add_learning(root, args.title, args.finding, args.competition, args.evidence)
    elif args.command == "archive":
        result = archive_learning(root, args.id, args.reason)
    else:
        result = {"ok": True, "learnings": list_learnings(root, args.competition, args.query)}
    sys.stdout.write(json.dumps(result) + "\n")


def slugify(text: str) -> str:
    """Lowercase alphanumeric slug for filenames."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "untitled"


def next_id(root: Path) -> int:
    """Next learning number from existing filenames."""
    ids = [int(m.group(1)) for f in root.glob("L-*.md") if (m := re.match(r"L-(\d+)-", f.name))]
    return max(ids, default=0) + 1


def add_learning(root: Path, title: str, finding: str, competition: str, evidence: str) -> dict:
    """Write one learning file. Returns its id and path."""
    if not title.strip() or not finding.strip():
        raise ValueError("title and finding must be non-empty")
    root.mkdir(parents=True, exist_ok=True)
    lid = next_id(root)
    path = root / f"L-{lid:03d}-{slugify(title)}.md"
    path.write_text(
        f"# {title.strip()}\nDate: {date.today().isoformat()}\nCompetition: {competition}\n"
        f"Finding: {finding.strip()}\nEvidence: {evidence.strip()}\nApplies when: \n"
    )
    return {"ok": True, "id": lid, "path": str(path)}


def list_learnings(root: Path, competition: str | None, query: str | None) -> list[dict]:
    """List learnings matching optional filters. Archived entries excluded."""
    results: list[dict] = []
    if not root.is_dir():
        return results
    for path in sorted(root.glob("L-*.md")):
        if (root / "archive" / path.name).exists():
            continue
        text = path.read_text()
        if competition and f"Competition: {competition}" not in text:
            continue
        if query and query.lower() not in text.lower():
            continue
        results.append({"path": str(path), "title": text.splitlines()[0].lstrip("# ")})
    return results


def archive_learning(root: Path, lid: int, reason: str) -> dict:
    """Move a learning to archive/ with a reason trailer. Never deletes."""
    matches = [f for f in root.glob(f"L-{lid:03d}-*.md") if f.is_file()]
    if not matches:
        raise ValueError(f"no learning with id {lid}")
    if not reason.strip():
        raise ValueError("archive reason must be non-empty")
    dest_dir = root / "archive"
    dest_dir.mkdir(parents=True, exist_ok=True)
    src = matches[0]
    text = src.read_text() + f"Archived: {date.today().isoformat()} ({reason.strip()})\n"
    (dest_dir / src.name).write_text(text)
    src.unlink()
    return {"ok": True, "id": lid, "archived": str(dest_dir / src.name)}


if __name__ == "__main__":
    main()
