"""Download competition data and scaffold a workspace.

Wraps `kaggle competitions download` with resume-safe defaults, extracts the
archive, and creates the workspace layout from competition.md. Emits JSON to
stdout; diagnostics to stderr.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import BlockedError, UsageError, emit, log, run, run_cli


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download competition data and scaffold a workspace.")
    parser.add_argument("slug", help="Competition slug (e.g. titanic).")
    parser.add_argument("--path", default=".", help="Parent directory for the workspace (default: cwd).")
    parser.add_argument("--file", default=None, help="Single file to download instead of the full archive.")
    parser.add_argument("--force", action="store_true", help="Restart download from zero (never for resume).")
    parser.add_argument("--no-unzip", action="store_true", help="Keep the archive without extracting.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    emit(initialize(args.slug, parent=Path(args.path), file=args.file, force=args.force, unzip=not args.no_unzip))


def initialize(slug: str, parent: Path, file: str | None, force: bool, unzip: bool) -> dict:
    """Download and scaffold; pure orchestration kept testable via monkeypatched steps."""
    if not slug or "/" in slug:
        raise UsageError(f"Invalid competition slug {slug!r}")
    workspace = parent / slug
    (workspace / "data").mkdir(parents=True, exist_ok=True)
    (workspace / "submissions").mkdir(parents=True, exist_ok=True)
    archive = download(slug, workspace / "data", file=file, force=force)
    extracted = extract(archive, unzip) if archive is not None else []
    readme = workspace / "README.md"
    if not readme.is_file():
        readme.write_text(f"# {slug}\n\nRules: https://www.kaggle.com/competitions/{slug}\n")
    return {
        "ok": True,
        "workspace": str(workspace),
        "archive": str(archive) if archive else None,
        "extracted": extracted,
    }


def download(slug: str, dest: Path, file: str | None, force: bool) -> Path | None:
    """Run the CLI download. Returns the archive path, or None for single files."""
    cmd = ["competitions", "download", "-c", slug, "-p", str(dest)]
    if file:
        cmd += ["-f", file]
    if force:
        cmd += ["--force"]
        log("WARNING: --force restarts the download from zero; omit it to resume")
    code, out, err = run_cli(cmd, timeout=3600)
    if code != 0:
        raise BlockedError(f"download failed: {(err or out).strip()[-300:]}", f"accept rules at kaggle.com/c/{slug}")
    if "Skipping, found more recently modified local copy" in out:
        raise BlockedError("local copy is newer than remote", f"delete {dest} partial files or pass --force to restart")
    name = file if file else f"{slug}.zip"
    path = dest / name
    return path if path.is_file() else None


def extract(archive: Path | None, unzip: bool) -> list[str]:
    """Extract a zip archive in place. Returns extracted member names."""
    import zipfile

    if archive is None or not unzip or not zipfile.is_zipfile(archive):
        return []
    with zipfile.ZipFile(archive) as zf:
        members = zf.namelist()
        zf.extractall(archive.parent)
    return members


if __name__ == "__main__":
    run(main)
