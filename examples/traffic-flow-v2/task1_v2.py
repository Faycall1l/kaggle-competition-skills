"""Task 1 v2: neighbor-augmented reconstruction (L1 temporal + L2 spatial).

Extends the historical-mean baseline (L0): for each blanked target cell, use
the nearest eligible same-link observations in time first, then the eligible
upstream/downstream link values at the same timestamp, falling back to the
link profile. Speeds are clamped to the link free speed from the network
files. Output columns match the v1 builder exactly.

Dependency: the baselines `src/` tree
(https://github.com/jacky850/trafficflowbench-public) must be importable, so
`task1.baseline_task1_historical_mean` resolves. In the kernel bundle it ships
under `src/`; locally point PYTHONPATH at the cloned repository.

Eligibility follows the contract: pct_observed >= 75 with finite channels.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import sys as _sys
from pathlib import Path as _Path

# Same bootstrap as the v1 builders: this file ships at src/task1/task1_v2.py,
# so parent.parent is the src/ directory that makes `task1.*` importable.
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))


def _baseline():
    """Import baseline helpers lazily; the baselines src tree is a runtime dependency."""
    try:
        from task1.baseline_task1_historical_mean import (
            HERE,
            build_profile,
            check_release_root,
            masked_files,
            slot_values,
        )
    except ImportError as exc:
        raise SystemExit(
            "task1_v2 needs the baselines src/ tree importable "
            "(https://github.com/jacky850/trafficflowbench-public): " + str(exc)
        )
    return build_profile, check_release_root, masked_files, slot_values, HERE


OUTPUT_COLUMNS = ["panel", "timestamp", "station_id", "link_id", "mask_regime", "speed_kmh", "flow_vph"]
TEMPORAL_HALF_WINDOW = 6  # steps (5-minute slots) searched each direction
FREE_SPEED_CANDIDATES = ("free_speed_kmh", "free_speed", "freeflow_speed_kmh", "free_flow_speed")


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


def free_speed_by_link(panel_dir: Path) -> dict[str, float]:
    """Free speed per link id from links.csv; empty when the column is absent."""
    path = panel_dir / "network" / "links.csv"
    speeds: dict[str, float] = {}
    if not path.is_file():
        return speeds
    frame = pd.read_csv(path, dtype=str)
    column = next((c for c in FREE_SPEED_CANDIDATES if c in frame.columns), None)
    if column is None and "free speed" in frame.columns:
        column = "free speed"
    if column is None:
        return speeds
    values = pd.to_numeric(frame[column], errors="coerce")
    for link_id, speed in zip(frame["link_id"].astype(str), values):
        if np.isfinite(speed) and speed > 0:
            speeds[link_id] = float(speed)
    return speeds


def eligible(frame: pd.DataFrame) -> np.ndarray:
    """Eligible observed cells per the contract."""
    return (
        pd.to_numeric(frame["pct_observed"], errors="coerce").ge(75)
        & frame["speed_kmh"].notna()
        & frame["flow_vph"].notna()
    ).to_numpy()


def temporal_fill(values: np.ndarray, valid: np.ndarray, half_window: int = TEMPORAL_HALF_WINDOW) -> np.ndarray:
    """Nearest eligible observation in time per position; NaN when none in window."""
    n = len(values)
    filled = np.full(n, np.nan)
    valid_idx = np.flatnonzero(valid)
    if len(valid_idx) == 0:
        return filled
    positions = np.arange(n)
    prev = np.searchsorted(valid_idx, positions, side="right") - 1
    nxt = np.searchsorted(valid_idx, positions, side="left")
    has_prev = (prev >= 0) & (positions - valid_idx[np.clip(prev, 0, len(valid_idx) - 1)] <= half_window)
    has_next = (nxt < len(valid_idx)) & (valid_idx[np.clip(nxt, 0, len(valid_idx) - 1)] - positions <= half_window)
    prev_val = np.where(has_prev, values[valid_idx[np.clip(prev, 0, len(valid_idx) - 1)]], np.nan)
    next_val = np.where(has_next, values[valid_idx[np.clip(nxt, 0, len(valid_idx) - 1)]], np.nan)
    both = np.isfinite(prev_val) & np.isfinite(next_val)
    filled = np.where(both, 0.5 * (prev_val + next_val), np.where(np.isfinite(prev_val), prev_val, next_val))
    filled[valid] = values[valid]
    return filled


def build_panel_submission(
    panel: str,
    release: Path,
    split: str,
    output: Path,
    write_header: bool,
    topology: dict | None = None,
    half_window: int = TEMPORAL_HALF_WINDOW,
) -> int:
    """Write v2 predictions for one panel. Returns rows written."""
    from task1.build_task1_baseline_submission import OUTPUT_COLUMNS as _cols

    assert _cols == OUTPUT_COLUMNS, "v2 output contract drifted from v1 builder"
    build_profile, check_release_root, masked_files, slot_values, _ = _baseline()
    check_release_root(release, panel)
    panel_dir = release / "corridors" / panel
    speed_profile, flow_profile, profile_counts = build_profile(panel, panel_dir)
    link_index = speed_profile["link_index"]
    neighbours = topology if topology is not None else load_topology(panel_dir)
    free_speed = free_speed_by_link(panel_dir)
    template = pd.read_csv(
        panel_dir.parent.parent / "task1" / panel_dir.name / split / "sample_submission_state.csv",
        usecols=["timestamp", "station_id", "link_id"],
        dtype=str,
    )
    template_keys = set(zip(template.timestamp, template.station_id, template.link_id))
    rows_written = 0
    for path in masked_files(panel_dir, split):
        frame = pd.read_parquet(
            path,
            columns=["timestamp", "station_id", "link_id", "speed_kmh", "flow_vph", "pct_observed", "mask_regime"],
        ).sort_values(["link_id", "timestamp"], kind="stable")
        frame["station_id"] = frame.station_id.astype(str)
        frame["link_id"] = frame.link_id.astype(str)
        weekday, tod = slot_values(frame)
        slot = weekday * 288 + tod
        li = frame.link_id.map(link_index).fillna(-1).to_numpy(dtype=np.int64)
        known = li >= 0
        safe_li = np.where(known, li, 0)
        base_speed = np.where(
            profile_counts["speed_count"][safe_li, slot] == 0,
            speed_profile["fallback"][safe_li],
            speed_profile["mean"][safe_li, slot],
        )
        base_flow = np.where(
            profile_counts["flow_count"][safe_li, slot] == 0,
            flow_profile["fallback"][safe_li],
            flow_profile["mean"][safe_li, slot],
        )
        speed = pd.to_numeric(frame.speed_kmh, errors="coerce").to_numpy(dtype=float)
        flow = pd.to_numeric(frame.flow_vph, errors="coerce").to_numpy(dtype=float)
        ok = eligible(frame)
        # L1: temporal interpolation within each link's own series.
        t_speed = np.full_like(speed, np.nan)
        t_flow = np.full_like(flow, np.nan)
        for _, group in frame.groupby("link_id", sort=False).indices.items():
            idx = np.asarray(group)
            t_speed[idx] = temporal_fill(speed[idx], ok[idx], half_window)
            t_flow[idx] = temporal_fill(flow[idx], ok[idx], half_window)
        # L2: same-timestamp neighbour average.
        neighbour_speed = np.full_like(speed, np.nan)
        neighbour_flow = np.full_like(flow, np.nan)
        by_time: dict[str, np.ndarray] = {}
        times = frame.timestamp.astype(str).to_numpy()
        for t in np.unique(times):
            by_time[t] = np.flatnonzero(times == t)
        link_of = frame.link_id.to_numpy()
        for i in range(len(frame)):
            links = neighbours.get(str(link_of[i]), {})
            pool = links.get("upstream", []) + links.get("downstream", [])
            if not pool:
                continue
            idx = by_time[str(times[i])]
            pool_mask = np.isin(link_of[idx], pool) & ok[idx]
            if pool_mask.any():
                neighbour_speed[i] = np.nanmean(speed[idx][pool_mask])
                neighbour_flow[i] = np.nanmean(flow[idx][pool_mask])
        # Priority: temporal, then spatial, then profile.
        pred_speed = np.where(
            np.isfinite(t_speed), t_speed, np.where(np.isfinite(neighbour_speed), neighbour_speed, base_speed)
        )
        pred_flow = np.where(
            np.isfinite(t_flow), t_flow, np.where(np.isfinite(neighbour_flow), neighbour_flow, base_flow)
        )
        pred_speed = np.maximum(pred_speed, 0.0)
        pred_flow = np.maximum(pred_flow, 0.0)
        for i in range(len(frame)):
            cap = free_speed.get(str(link_of[i]))
            if cap is not None and np.isfinite(pred_speed[i]):
                pred_speed[i] = min(pred_speed[i], cap * 1.05)
        blanked = np.fromiter(
            (
                k in template_keys
                for k in zip(frame.timestamp.astype(str), frame.station_id.astype(str), frame.link_id.astype(str))
            ),
            dtype=bool,
            count=len(frame),
        )
        for regime in pd.unique(frame.mask_regime.astype(str)):
            target = blanked & (frame.mask_regime.astype(str) == regime).to_numpy()
            mask = target & known & np.isfinite(pred_speed) & np.isfinite(pred_flow)
            if not mask.any():
                continue
            out = pd.DataFrame(
                {
                    "panel": panel,
                    "timestamp": frame.loc[mask, "timestamp"].astype(str).to_numpy(),
                    "station_id": frame.loc[mask, "station_id"].to_numpy(),
                    "link_id": frame.loc[mask, "link_id"].to_numpy(),
                    "mask_regime": regime,
                    "speed_kmh": pred_speed[mask],
                    "flow_vph": pred_flow[mask],
                },
                columns=OUTPUT_COLUMNS,
            )
            out.to_csv(output, mode="w" if write_header else "a", header=write_header, index=False)
            write_header = False
            rows_written += len(out)
    return rows_written


def main() -> None:
    ap = argparse.ArgumentParser(description="Task 1 v2 neighbor-augmented submission builder.")
    ap.add_argument("--release-root", type=Path, required=True)
    ap.add_argument("--split", choices=["train", "validation", "private"], default="validation")
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--panel", action="append", help="build only selected panel(s)")
    ap.add_argument("--half-window", type=int, default=TEMPORAL_HALF_WINDOW)
    args = ap.parse_args()
    _, _, _, _, _baseline_here = _baseline()
    panels_manifest = json.loads((_baseline_here / "config" / "corridors.json").read_text(encoding="utf-8"))
    panels = [p["corridor_id"] for p in panels_manifest["panels"]]
    if args.panel:
        panels = [p for p in panels if p in set(args.panel)]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        args.output.unlink()
    total, first = 0, True
    for panel in panels:
        print(f"[Task1 v2] {panel}", flush=True)
        count = build_panel_submission(
            panel, args.release_root.resolve(), args.split, args.output.resolve(), first, half_window=args.half_window
        )
        total += count
        first = False
        print(f"  wrote {count:,} target rows", flush=True)
    print(f"Wrote {total:,} rows to {args.output.resolve()}")


if __name__ == "__main__":
    main()
