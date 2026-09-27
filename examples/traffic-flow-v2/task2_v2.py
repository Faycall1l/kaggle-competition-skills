"""Task 2 v2: shockwave-propagated queue forecast.

Extends persistence: ongoing queues persist, flickering links latch, and
onset is predicted by advecting the observed queue boundary upstream at finite
wave speed. Dissipating queues clear after two horizon steps.

Queues propagate opposite the travel direction: a queued downstream link
implies upstream links will queue within the horizon. Onset windows (no
established queue in history) score ~0 under pure persistence; any true
overlap improves them.

Output columns match the v1 builder exactly.
"""

from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path

import pandas as pd

import sys as _sys
from pathlib import Path as _Path

# Same bootstrap as the v1 builders: this file ships at src/task2/task2_v2.py,
# so parent.parent is the src/ directory that makes `task2.*` importable.
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))


def _v1():
    """Import v1 helpers lazily; the baselines src/ tree is a runtime dependency."""
    try:
        from task2.build_task2_persistence_submission import (
            read_queue_template,
            read_window_history,
            read_window_index,
        )
        from task2.queue_utils import thresholds
    except ImportError as exc:
        raise SystemExit(
            "task2_v2 needs the baselines src/ tree importable "
            "(https://github.com/jacky850/trafficflowbench-public): " + str(exc)
        )
    return read_queue_template, read_window_history, read_window_index, thresholds


def upstream_hops(topology: dict[str, dict[str, list[str]]], start: str, max_hops: int = 6) -> dict[str, int]:
    """BFS hop distance from start following incoming (upstream) edges."""
    dist: dict[str, int] = {start: 0}
    queue: deque[str] = deque([start])
    while queue:
        node = queue.popleft()
        if dist[node] >= max_hops:
            continue
        for parent in topology.get(node, {}).get("upstream", []):
            if parent not in dist:
                dist[parent] = dist[node] + 1
                queue.append(parent)
    return dist


def load_topology(panel_dir: Path) -> dict[str, dict[str, list[str]]]:
    """Map link_id -> {upstream, downstream} from lwr_mainline_topology.csv."""
    path = panel_dir / "network" / "lwr_mainline_topology.csv"
    neighbours: dict[str, dict[str, list[str]]] = {}
    if not path.is_file():
        return neighbours
    topo = pd.read_csv(path, dtype=str).fillna("")
    for _, row in topo.iterrows():
        link = str(row.get("link_id", ""))
        if not link:
            continue
        neighbours[link] = {
            "upstream": [x for x in str(row.get("incoming_link_ids", "")).split(";") if x],
            "downstream": [x for x in str(row.get("outgoing_link_ids", "")).split(";") if x],
        }
    return neighbours


def forecast_window(
    hist: pd.DataFrame,
    template: pd.DataFrame,
    threshold: dict[str, float],
    topology: dict[str, dict[str, list[str]]],
    onset_radius: int = 2,
) -> pd.DataFrame:
    """Predict queue_pred for one window's template rows.

    hist: history rows (timestamp, link_id, speed_kmh, is_score_eligible).
    template: target rows (window_id, timestamp, link_id), chronological.
    """
    hist = hist.copy()
    hist["link_id"] = hist.link_id.astype(str)
    hist["timestamp"] = pd.to_datetime(hist.timestamp, utc=True)
    hist = hist.sort_values("timestamp")
    steps = sorted(hist.timestamp.unique())
    hist["step"] = hist.timestamp.map({t: i for i, t in enumerate(steps)})
    hist["queued"] = (
        pd.to_numeric(hist.speed_kmh, errors="coerce") <= hist.link_id.map(threshold).fillna(63.0)
    ) & hist["is_score_eligible"].astype(bool)
    last = hist.step.max()
    queued_now = set(hist.loc[hist.step == last].query("queued").link_id)
    queued_early = set(hist.loc[hist.step <= last - 6].query("queued").link_id) if last >= 6 else set()
    growing = len(queued_now) > len(queued_early)
    latched = set(hist.loc[hist.step >= last - 1].query("queued").link_id)
    # Upstream neighbourhood of currently queued links (onset candidates).
    onset_links: set[str] = set()
    if growing:
        for link in queued_now:
            for upstream, dist in upstream_hops(topology, link).items():
                if 1 <= dist <= onset_radius:
                    onset_links.add(upstream)
    onset_links -= queued_now
    template = template.copy()
    template["link_id"] = template.link_id.astype(str)
    template["timestamp"] = pd.to_datetime(template.timestamp, utc=True)
    template = template.sort_values("timestamp")
    horizon = sorted(template.timestamp.unique())
    step_of = {t: k for k, t in enumerate(horizon)}
    preds = []
    for _, row in template.iterrows():
        link = row.link_id
        if link in queued_now or link in latched:
            preds.append(1)
        elif link in onset_links:
            preds.append(1)
        else:
            preds.append(0)
    # Dissipation: queued set shrinking fast clears late horizon steps.
    if queued_early and len(queued_now) * 2 < len(queued_early):
        template = template.reset_index(drop=True)
        for i, row in template.iterrows():
            if row.link_id in queued_now and step_of[row.timestamp] >= 2:
                preds[i] = 0
    out = template[["window_id", "timestamp", "link_id"]].copy()
    out["queue_pred"] = preds
    return out


def main() -> None:
    read_queue_template, read_window_history, read_window_index, thresholds = _v1()
    ap = argparse.ArgumentParser(description="Task 2 v2 shockwave-propagated submission builder.")
    ap.add_argument("--release-root", type=Path, required=True)
    ap.add_argument("--split", choices=["train", "validation", "private", "all"], default="validation")
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--panel", action="append", help="build only selected panel(s)")
    ap.add_argument("--onset-radius", type=int, default=2)
    args = ap.parse_args()
    root = args.release_root.resolve()
    splits = ["train", "validation"] if args.split == "all" else [args.split]
    windows = read_window_index(root, splits)
    history = read_window_history(root, splits)
    template = read_queue_template(root, splits)
    if args.panel:
        windows = windows[windows.panel.astype(str).isin(set(args.panel))]
    panel_of_window = windows.set_index("window_id").panel.astype(str).to_dict()
    thresholds_by_panel: dict[str, dict[str, float]] = {}
    topology_by_panel: dict[str, dict] = {}
    for panel in sorted(windows.panel.astype(str).unique()):
        panel_dir = root / "corridors" / panel
        links = pd.read_csv(panel_dir / "network" / "links.csv")
        links["link_id"] = links.link_id.astype(str)
        thresholds_by_panel[panel], _ = thresholds(panel_dir, links)
        topology_by_panel[panel] = load_topology(panel_dir)
    targets = []
    for window_id, group in template.groupby("window_id", sort=True):
        panel = panel_of_window.get(str(window_id))
        if panel is None:
            continue
        hist = history[history.window_id.astype(str) == str(window_id)]
        if hist.empty:
            continue
        targets.append(
            forecast_window(hist, group, thresholds_by_panel[panel], topology_by_panel[panel], args.onset_radius)
        )
    if not targets:
        raise RuntimeError("No queue v2 rows were generated")
    out = pd.concat(targets, ignore_index=True).drop_duplicates(["window_id", "timestamp", "link_id"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output, index=False)
    print(f"Wrote {len(out):,} rows to {args.output.resolve()}")


if __name__ == "__main__":
    main()
