#!/bin/sh
# Stop hook: nudge a retrospective when Kaggle work happened this session.
# Read-only: prints a reminder, never modifies state. Exits 0 always.
set -u

echo "kaggle-learnings: if this session produced surprises or validated patterns, run retrospect (kln.py add) before closing."
exit 0
