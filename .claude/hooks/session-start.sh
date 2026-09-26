#!/bin/sh
# Session-start hook: inject top learnings into agent context.
# Reads .learnings/ digest (LEARNINGS.md preferred, else newest files).
# Read-only: never modifies state. Exits 0 always.
set -u

WORKSPACE="${CLAUDE_PROJECT_DIR:-$PWD}"
LEARNINGS_DIR="$WORKSPACE/.learnings"

if [ -f "$WORKSPACE/LEARNINGS.md" ]; then
  echo "--- kaggle learnings digest ---"
  head -n 40 "$WORKSPACE/LEARNINGS.md"
elif [ -d "$LEARNINGS_DIR" ]; then
  echo "--- kaggle learnings (latest) ---"
  # shellcheck disable=SC2012
  ls -t "$LEARNINGS_DIR"/L-*.md 2>/dev/null | head -n 5 | while IFS= read -r f; do
    head -n 8 "$f"
    echo
  done
fi
exit 0
