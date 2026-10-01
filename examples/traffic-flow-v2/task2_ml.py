"""Task 2 ML: pseudo-labeled queue classifier.

Queue labels are withheld on every split, so supervised training uses the
train split's UNMASKED observations with the released queue definition
(speed <= v_cut threshold and eligible). The classifier learns
P(queue in horizon | history) from threshold-rule labels, then predicts the
released validation/private windows.

Features per (link, horizon step) use only the 60-minute released history:
own speed aggregates, eligibility, slope, neighbour queued fractions,
upstream hop distance to the nearest queued link, threshold, time of day,
and the horizon step index. No future information enters.

Modes: `train` writes model.pkl; `predict` loads it and writes the queue
submission CSV with v1-compatible columns.
"""

from __future__ import annotations

import argparse
import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

import sys as _sys
from pathlib import Path as _Path

# Same bootstrap as the v1 builders: this file ships at src/task2/task2_ml.py,
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
            "task2_ml needs the baselines src/ tree importable "
            "(https://github.com/jacky850/trafficflowbench-public): " + str(exc)
        )
    return read_queue_template, read_window_history, read_window_index, thresholds


HISTORY_STEPS = 12
HORIZON_STEPS = 6

FEATURE_COLUMNS = [
    "last_speed",
    "min_speed",
    "mean_speed",
    "slope",
    "eligible_frac",
    "neighbor_queued_frac",
    "upstream_hops",
    "threshold",
    "tod_slot",
    "horizon_step",
]

FEATURE_COLUMNS_V2 = FEATURE_COLUMNS + [
    "last_flow",
    "mean_flow",
    "flow_slope",
    "last_occupancy",
    "speed_drop",
    "upstream_speed",
    "downstream_speed",
    "ramp_inflow",
    "ramp_outflow",
    "density_proxy",
    "bottleneck_freq",
]


def bottleneck_frequencies(
    panel_dir: Path, threshold: dict[str, float], list_files=None  # type: ignore[no-untyped-def]
) -> dict[str, float]:
    """Per-link queue frequency over unmasked train history (recurrent-bottleneck prior).

    Train-month and later-month queue locations correlate strongly (measured
    rank correlation 0.93), so historical frequency predicts where queues form
    even when the current window shows nothing (onset case). `list_files`
    overrides the release file lookup (fixture tests).
    """
    if list_files is None:
        from task1.baseline_task1_historical_mean import files as _train_files

        list_files = _train_files

    freq: dict[str, float] = {}
    counts: dict[str, int] = {}
    for path in list_files(panel_dir, "train"):
        frame = pd.read_parquet(path, columns=["link_id", "speed_kmh", "is_score_eligible"])
        frame["link_id"] = frame.link_id.astype(str)
        queued = pd.to_numeric(frame.speed_kmh, errors="coerce") <= frame.link_id.map(threshold).fillna(63.0)
        queued &= frame.is_score_eligible.astype(bool)
        for link, flag in zip(frame.link_id, queued.to_numpy()):
            freq[link] = freq.get(link, 0.0) + float(flag)
            counts[link] = counts.get(link, 0) + 1
    return {link: freq[link] / max(counts[link], 1) for link in freq}


def slope_of(values: np.ndarray) -> float:
    """Least-squares slope over finite values; 0.0 when underdetermined."""
    finite = np.isfinite(values)
    if finite.sum() < 2:
        return 0.0
    x = np.flatnonzero(finite).astype(float)
    return float(np.polyfit(x, values[finite], 1)[0])


def row_features(
    link_speeds: np.ndarray,
    link_eligible: np.ndarray,
    neighbor_queued_frac: float,
    upstream_hops: int,
    threshold: float,
    tod_slot: int,
    horizon_step: int,
) -> list[float]:
    """Feature vector for one (link, horizon step). Pure function, unit-tested."""
    finite = link_speeds[np.isfinite(link_speeds)]
    last = float(finite[-1]) if len(finite) else threshold
    return [
        last,
        float(np.min(finite)) if len(finite) else threshold,
        float(np.mean(finite)) if len(finite) else threshold,
        slope_of(link_speeds),
        float(np.mean(link_eligible)) if len(link_eligible) else 0.0,
        float(neighbor_queued_frac),
        float(upstream_hops),
        float(threshold),
        float(tod_slot),
        float(horizon_step),
    ]


def label_horizon(future_speeds: np.ndarray, future_eligible: np.ndarray, threshold: float) -> np.ndarray:
    """Threshold-rule queue labels for horizon steps (train unmasked data only)."""
    speeds = pd.to_numeric(future_speeds, errors="coerce")
    eligible = pd.Series(future_eligible).astype(bool).to_numpy()
    return ((speeds <= threshold) & eligible).astype(int)


def _finite_tail(values: np.ndarray, default: float) -> tuple[float, float, float]:
    """(last, min, mean) over finite values with a fallback."""
    finite = np.asarray(values, dtype=float)[np.isfinite(np.asarray(values, dtype=float))]
    if len(finite) == 0:
        return default, default, default
    return float(finite[-1]), float(np.min(finite)), float(np.mean(finite))


def row_features_v2(
    link_speeds: np.ndarray,
    link_flows: np.ndarray,
    link_occ: np.ndarray,
    link_eligible: np.ndarray,
    neighbor_speeds: list,
    ramp_inflow: float,
    ramp_outflow: float,
    neighbor_queued_frac: float,
    upstream_hops: int,
    threshold: float,
    tod_slot: int,
    horizon_step: int,
    bottleneck: float = 0.0,
) -> list[float]:
    """Extended feature vector (v2).

    Adds flow and occupancy channels, the speed drop over the history window
    (breakdown precursor), lagged neighbour speeds, panel ramp flows, and an
    occupancy-based density proxy. Pure function, unit-tested.
    """
    last_speed, min_speed, mean_speed = _finite_tail(link_speeds, threshold)
    _, _, mean_flow = _finite_tail(link_flows, 0.0)
    last_flow = float(link_flows[np.isfinite(link_flows)][-1]) if np.isfinite(link_flows).any() else 0.0
    _, _, mean_occ = _finite_tail(link_occ, 0.0)
    first_speed = float(link_speeds[np.isfinite(link_speeds)][0]) if np.isfinite(link_speeds).any() else last_speed
    speed_drop = first_speed - last_speed
    finite_neigh = [v for v in neighbor_speeds if v is not None and np.isfinite(v)]
    upstream_speed = float(finite_neigh[0]) if finite_neigh else last_speed
    downstream_speed = float(finite_neigh[-1]) if finite_neigh else last_speed
    density_proxy = mean_occ
    return [
        last_speed,
        min_speed,
        mean_speed,
        slope_of(link_speeds),
        float(np.mean(link_eligible)) if len(link_eligible) else 0.0,
        float(neighbor_queued_frac),
        float(upstream_hops),
        float(threshold),
        float(tod_slot),
        float(horizon_step),
        last_flow,
        mean_flow,
        slope_of(link_flows),
        mean_occ,
        speed_drop,
        upstream_speed,
        downstream_speed,
        float(ramp_inflow) if np.isfinite(ramp_inflow) else 0.0,
        float(ramp_outflow) if np.isfinite(ramp_outflow) else 0.0,
        density_proxy,
        float(bottleneck) if np.isfinite(bottleneck) else 0.0,
    ]


def upstream_distances(
    topology: dict[str, dict[str, list[str]]], queued: set[str], max_hops: int = 6
) -> dict[str, int]:
    """Hop distance from each link to the nearest queued link (upstream search)."""
    from collections import deque

    dist: dict[str, int] = {}
    queue: deque[tuple[str, int]] = deque()
    for link in queued:
        dist[link] = 0
        queue.append((link, 0))
    while queue:
        node, depth = queue.popleft()
        if depth >= max_hops:
            continue
        for parent in topology.get(node, {}).get("upstream", []):
            if parent not in dist:
                dist[parent] = depth + 1
                queue.append((parent, depth + 1))
    return dist


def train_classifier(X: np.ndarray, y: np.ndarray, class_weight=None):  # type: ignore[no-untyped-def]
    """Gradient boosting on the feature matrix. Returns the fitted model."""
    from sklearn.ensemble import HistGradientBoostingClassifier

    model = HistGradientBoostingClassifier(
        max_iter=200, learning_rate=0.1, max_depth=5, random_state=0, class_weight=class_weight
    )
    model.fit(X, y)
    return model


def _topology(panel_dir: Path) -> dict[str, dict[str, list[str]]]:
    path = panel_dir / "network" / "lwr_mainline_topology.csv"
    neighbours: dict[str, dict[str, list[str]]] = {}
    if not path.is_file():
        return neighbours
    topo = pd.read_csv(path, dtype=str).fillna("")
    for _, row in topo.iterrows():
        link = str(row.get("link_id", ""))
        if link:
            neighbours[link] = {
                "upstream": [x for x in str(row.get("incoming_link_ids", "")).split(";") if x],
                "downstream": [x for x in str(row.get("outgoing_link_ids", "")).split(";") if x],
            }
    return neighbours


def _read_ramp_series(panel_dir: Path) -> pd.DataFrame | None:
    """Panel ramp counts per timestamp, schema-tolerant. None when unavailable."""
    candidates = sorted((panel_dir / "train" / "ramp_states").glob("**/*.parquet"))
    if not candidates:
        return None
    try:
        frame = pd.read_parquet(candidates[0])
    except (ValueError, OSError):
        return None
    time_col = next((c for c in ("timestamp", "date", "time") if c in frame.columns), None)
    if time_col is None:
        return None
    numeric = [c for c in frame.columns if c != time_col and pd.api.types.is_numeric_dtype(frame[c])]
    if not numeric:
        return None
    frame = frame.copy()
    frame["timestamp"] = pd.to_datetime(frame[time_col], utc=True)
    frame["ramp_count"] = frame[numeric].sum(axis=1, min_count=1)
    return frame.groupby("timestamp", sort=True)["ramp_count"].sum().reset_index()


def sample_training_rows(
    panel_dir: Path,
    threshold: dict[str, float],
    topology: dict[str, dict[str, list[str]]],
    stride: int = 48,
    max_origins: int = 400,
    before: str | None = None,
    after: str | None = None,
    list_files=None,  # type: ignore[no-untyped-def]
    feature_set: str = "v1",
) -> tuple[np.ndarray, np.ndarray]:
    """Sample (features, labels) from unmasked train observations.

    Origins stride through time deterministically; labels are the threshold
    rule on the following 6 steps. `before`/`after` (YYYY-MM-DD) restrict
    origins for time-split evaluation. Panel-agnostic: no link or panel ids
    leak into features, so one global model serves all panels. `list_files`
    overrides the release file lookup (fixture tests). `feature_set` selects
    the v1 vector or the extended v2 vector (flow/occupancy/deltas/ramps).
    """
    if list_files is None:
        from task1.baseline_task1_historical_mean import files as _train_files

        list_files = _train_files

    frames = []
    columns = ["timestamp", "link_id", "speed_kmh", "is_score_eligible"]
    if feature_set == "v2":
        columns += ["flow_vph", "occupancy"]
    for path in list_files(panel_dir, "train"):
        try:
            frames.append(pd.read_parquet(path, columns=columns))
        except (ValueError, KeyError):
            frames.append(pd.read_parquet(path))
    if not frames:
        width = len(FEATURE_COLUMNS_V2) if feature_set == "v2" else len(FEATURE_COLUMNS)
        return np.zeros((0, width)), np.zeros(0, dtype=int)
    frame = pd.concat(frames, ignore_index=True)
    frame["link_id"] = frame.link_id.astype(str)
    frame["timestamp"] = pd.to_datetime(frame.timestamp, utc=True)
    frame = frame.sort_values(["link_id", "timestamp"])
    frame["speed"] = pd.to_numeric(frame.speed_kmh, errors="coerce")
    frame["eligible"] = frame.is_score_eligible.astype(bool)
    if feature_set == "v2":
        frame["flow"] = pd.to_numeric(frame["flow_vph"], errors="coerce") if "flow_vph" in frame else np.nan
        frame["occ"] = pd.to_numeric(frame["occupancy"], errors="coerce") if "occupancy" in frame else np.nan
        ramps = _read_ramp_series(panel_dir)
    else:
        ramps = None

    def _window_arrays(group: pd.DataFrame) -> tuple | None:
        speeds = group.speed.to_numpy()
        eligible = group.eligible.to_numpy(dtype=bool)
        times = pd.DatetimeIndex(group.timestamp).tz_convert(None).to_numpy()
        flows = group.flow.to_numpy(dtype=float) if "flow" in group else np.full(len(group), np.nan)
        occs = group.occ.to_numpy(dtype=float) if "occ" in group else np.full(len(group), np.nan)
        if before is not None:
            keep = times < np.datetime64(before)
            speeds, eligible, times, flows, occs = speeds[keep], eligible[keep], times[keep], flows[keep], occs[keep]
        if after is not None:
            keep = times >= np.datetime64(after)
            speeds, eligible, times = speeds[keep], eligible[keep], times[keep]
            flows, occs = flows[keep], occs[keep]
        if len(speeds) < HISTORY_STEPS + HORIZON_STEPS:
            return None
        return speeds, eligible, times, flows, occs

    series: dict[str, pd.DataFrame] = {link: group for link, group in frame.groupby("link_id", sort=False)}
    filtered: dict[str, tuple] = {}
    for link, group in series.items():
        arrays = _window_arrays(group)
        if arrays is not None:
            filtered[str(link)] = arrays
    # Note: neighbor lookup aligns by position, assuming the shared 5-minute
    # calendar (missing reports are NaN rows, not missing rows).
    ramp_lookup: dict = {}
    if ramps is not None:
        for _, row in ramps.iterrows():
            ramp_lookup[str(row["timestamp"])] = float(row["ramp_count"])
    X_rows: list[list[float]] = []
    y_rows: list[int] = []
    bottlenecks = bottleneck_frequencies(panel_dir, threshold, list_files) if feature_set == "v2" else {}
    for link, (speeds, eligible, times, flows, occs) in filtered.items():
        limit = threshold.get(str(link), 63.0)
        neighbours = topology.get(str(link), {}).get("upstream", []) + topology.get(str(link), {}).get("downstream", [])
        origins = range(0, len(speeds) - HISTORY_STEPS - HORIZON_STEPS + 1, stride)[:max_origins]
        for origin in origins:
            last = origin + HISTORY_STEPS - 1
            near_frac, near_hops = 0.0, 6
            if neighbours:
                states = []
                for other in neighbours:
                    if other in filtered:
                        osp = filtered[other][0][last]
                        oel = filtered[other][1][last]
                        olim = threshold.get(other, 63.0)
                        states.append(bool(np.isfinite(osp) and osp <= olim and oel))
                if states:
                    near_frac = float(sum(states) / len(states))
                    near_hops = 1 if any(states) else 6
            hist_speeds = speeds[origin : origin + HISTORY_STEPS]
            hist_elig = eligible[origin : origin + HISTORY_STEPS]
            future_speeds = speeds[origin + HISTORY_STEPS : origin + HISTORY_STEPS + HORIZON_STEPS]
            future_elig = eligible[origin + HISTORY_STEPS : origin + HISTORY_STEPS + HORIZON_STEPS]
            labels = label_horizon(future_speeds, future_elig, limit)
            stamp = pd.Timestamp(times[last])
            tod_slot = int(stamp.hour * 12 + stamp.minute // 5)
            if feature_set == "v2":
                hist_flows = flows[origin : origin + HISTORY_STEPS]
                hist_occs = occs[origin : origin + HISTORY_STEPS]
                neigh_speeds = []
                for other in neighbours:
                    if other in filtered:
                        neigh_speeds.append(float(filtered[other][0][last]))
                window_times = [str(pd.Timestamp(t).isoformat()) for t in times[origin : origin + HISTORY_STEPS]]
                ramp_in = float(np.mean([ramp_lookup.get(t, 0.0) for t in window_times]))
                for k in range(HORIZON_STEPS):
                    X_rows.append(
                        row_features_v2(
                            hist_speeds,
                            hist_flows,
                            hist_occs,
                            hist_elig,
                            neigh_speeds,
                            ramp_in,
                            ramp_in,
                            near_frac,
                            near_hops,
                            limit,
                            tod_slot,
                            k,
                            bottlenecks.get(str(link), 0.0),
                        )
                    )
                    y_rows.append(int(labels[k]))
                continue
            for k in range(HORIZON_STEPS):
                X_rows.append(row_features(hist_speeds, hist_elig, near_frac, near_hops, limit, tod_slot, k))
                y_rows.append(int(labels[k]))
    width = len(FEATURE_COLUMNS_V2) if feature_set == "v2" else len(FEATURE_COLUMNS)
    X = np.array(X_rows, dtype=float).reshape(-1, width)
    return X, np.array(y_rows, dtype=int)


def precision_recall_f1(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    """Binary scores for the positive (queued) class."""
    tp = int(((y_true == 1) & (y_pred == 1)).sum())
    fp = int(((y_true == 0) & (y_pred == 1)).sum())
    fn = int(((y_true == 1) & (y_pred == 0)).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "positive_rate": float((y_pred == 1).mean()) if len(y_pred) else 0.0,
    }


def expected_positives(hist: pd.DataFrame, threshold: dict[str, float], growth_cap: float, floor: int) -> int:
    """Estimate queued cells in the horizon from history growth.

    Counts threshold-rule queued links now vs 6 steps ago; scales by the
    growth ratio clamped to [1/growth_cap, growth_cap], floored because every
    scored window contains queue somewhere.
    """
    now = hist.loc[hist.step == hist.step.max()]
    then = hist.loc[hist.step == max(hist.step.min(), hist.step.max() - 6)]
    queued_now = int(
        (
            (pd.to_numeric(now.speed_kmh, errors="coerce") <= now.link_id.map(threshold).fillna(63.0))
            & now.is_score_eligible.astype(bool)
        ).sum()
    )
    queued_then = int(
        (
            (pd.to_numeric(then.speed_kmh, errors="coerce") <= then.link_id.map(threshold).fillna(63.0))
            & then.is_score_eligible.astype(bool)
        ).sum()
    )
    if queued_then == 0:
        return max(queued_now, floor)
    growth = min(max(queued_now / queued_then, 1.0 / growth_cap), growth_cap)
    return max(int(round(queued_now * growth)), floor)


def _read_history_full(root: Path, splits: list[str]) -> pd.DataFrame:
    """Window history with all columns (flow/occupancy for v2 features)."""
    flat = root / "task2" / "window_history.parquet"
    if flat.exists():
        return pd.read_parquet(flat)
    parts = []
    for panel_dir in sorted(p for p in (root / "task2").glob("*") if p.is_dir()):
        for split in splits:
            candidate = panel_dir / split / "window_history.parquet"
            if candidate.exists():
                parts.append(candidate)
    if not parts:
        raise FileNotFoundError(f"no Task 2 window history under {root / 'task2'}")
    return pd.concat([pd.read_parquet(p) for p in parts], ignore_index=True)


def predict_windows(
    model,  # type: ignore[no-untyped-def]
    root: Path,
    splits: list[str],
    threshold: dict[str, dict[str, float]],
    topology: dict[str, dict],
    calibrate: bool = False,
    growth_cap: float = 3.0,
    floor: int = 2,
    decision_threshold: float = 0.5,
    feature_set: str = "v1",
) -> pd.DataFrame:
    """Predict queue_pred for released windows. Returns v1-compatible rows.

    Default is the fixed 0.5 decision threshold. With calibrate=True, each
    window's expected positive count is estimated from queue growth in
    history (current queued count scaled by the now-vs-6-steps-ago ratio,
    clamped, with a floor because every scored window contains queue), and
    the top-K cells by predicted probability are labeled 1.
    """
    from task2.build_task2_persistence_submission import read_queue_template

    _, read_window_history, read_window_index, _ = _v1()
    windows = read_window_index(root, splits)
    history = _read_history_full(root, splits) if feature_set == "v2" else read_window_history(root, splits)
    template = read_queue_template(root, splits)
    panel_of_window = windows.set_index("window_id").panel.astype(str).to_dict()
    history["link_id"] = history.link_id.astype(str)
    history["timestamp"] = pd.to_datetime(history.timestamp, utc=True)
    targets = []
    for window_id, group in template.groupby("window_id", sort=True):
        panel = panel_of_window.get(str(window_id))
        if panel is None:
            continue
        hist = history[history.window_id.astype(str) == str(window_id)].copy()
        if hist.empty:
            continue
        hist = hist.sort_values("timestamp")
        steps = sorted(hist.timestamp.unique())
        hist["step"] = hist.timestamp.map({t: i for i, t in enumerate(steps)})
        last = hist.step.max()
        last_rows = hist.loc[hist.step == last]
        queued_now = set(
            last_rows.loc[
                (
                    pd.to_numeric(last_rows.speed_kmh, errors="coerce")
                    <= last_rows.link_id.map(threshold[panel]).fillna(63.0)
                )
                & last_rows.is_score_eligible.astype(bool)
            ].link_id
        )
        dist = upstream_distances(topology[panel], queued_now)
        link_hist: dict[str, pd.DataFrame] = {link: g for link, g in hist.groupby("link_id", sort=False)}
        bottlenecks: dict[str, float] = {}
        if feature_set == "v2":
            bottlenecks = bottleneck_frequencies(root / "corridors" / panel, threshold[panel])
        ramp_lookup: dict = {}
        if feature_set == "v2":
            panel_dir = root / "corridors" / panel
            ramp_frame = _read_ramp_series(panel_dir)
            if ramp_frame is not None:
                for _, ramp_row in ramp_frame.iterrows():
                    ramp_lookup[str(ramp_row["timestamp"])] = float(ramp_row["ramp_count"])
        group = group.copy()
        group["link_id"] = group.link_id.astype(str)
        group["timestamp"] = pd.to_datetime(group.timestamp, utc=True)
        group = group.sort_values("timestamp")
        horizon = sorted(group.timestamp.unique())
        step_of = {t: k for k, t in enumerate(horizon)}
        feat_rows: list[list[float]] = []
        meta_rows: list[tuple] = []
        for _, row in group.iterrows():
            link = row.link_id
            g = link_hist.get(link)
            if g is None or len(g) < 6:
                speeds = np.full(HISTORY_STEPS, np.nan)
                elig = np.zeros(HISTORY_STEPS, dtype=bool)
                flows = np.full(HISTORY_STEPS, np.nan)
                occs = np.full(HISTORY_STEPS, np.nan)
            else:
                g = g.sort_values("step").tail(HISTORY_STEPS)
                speeds = pd.to_numeric(g.speed_kmh, errors="coerce").to_numpy(dtype=float)
                elig = g.is_score_eligible.astype(bool).to_numpy(dtype=bool)
                flows = (
                    pd.to_numeric(g.flow_vph, errors="coerce").to_numpy(dtype=float)
                    if "flow_vph" in g
                    else np.full(len(speeds), np.nan)
                )
                occs = (
                    pd.to_numeric(g.occupancy, errors="coerce").to_numpy(dtype=float)
                    if "occupancy" in g
                    else np.full(len(speeds), np.nan)
                )
                pad = HISTORY_STEPS - len(speeds)
                if pad > 0:
                    speeds = np.concatenate([np.full(pad, np.nan), speeds])
                    elig = np.concatenate([np.zeros(pad, dtype=bool), elig])
                    flows = np.concatenate([np.full(pad, np.nan), flows])
                    occs = np.concatenate([np.full(pad, np.nan), occs])
            states = []
            neigh_speeds = []
            for other in topology[panel].get(link, {}).get("upstream", []) + topology[panel].get(link, {}).get(
                "downstream", []
            ):
                go = link_hist.get(other)
                if go is None or go.empty:
                    continue
                last_o = go.loc[go.step == go.step.max()]
                osp = pd.to_numeric(last_o.speed_kmh, errors="coerce").to_numpy(dtype=float)[0]
                oel = bool(last_o.is_score_eligible.astype(bool).to_numpy(dtype=bool)[0])
                olim = threshold[panel].get(other, 63.0)
                states.append(bool(np.isfinite(osp) and osp <= olim and oel))
                neigh_speeds.append(float(osp) if np.isfinite(osp) else None)
            near_frac = float(sum(states) / len(states)) if states else 0.0
            limit = threshold[panel].get(link, 63.0)
            stamp = row.timestamp
            if feature_set == "v2":
                ramp_in = float(ramp_lookup.get(str(stamp), 0.0))
                feat_rows.append(
                    row_features_v2(
                        speeds,
                        flows,
                        occs,
                        elig,
                        neigh_speeds,
                        ramp_in,
                        ramp_in,
                        near_frac,
                        dist.get(link, 6),
                        limit,
                        int(stamp.hour * 12 + stamp.minute // 5),
                        step_of[stamp],
                        bottlenecks.get(link, 0.0),
                    )
                )
            else:
                feat_rows.append(
                    row_features(
                        speeds,
                        elig,
                        near_frac,
                        dist.get(link, 6),
                        limit,
                        int(stamp.hour * 12 + stamp.minute // 5),
                        step_of[stamp],
                    )
                )
            meta_rows.append((row.window_id, stamp, link))
        preds = (model.predict_proba(np.array(feat_rows, dtype=float))[:, 1] >= decision_threshold).astype(int)
        frame = pd.DataFrame(meta_rows, columns=["window_id", "timestamp", "link_id"])
        if calibrate:
            proba = model.predict_proba(np.array(feat_rows, dtype=float))[:, 1]
            expected = expected_positives(hist, threshold[panel], growth_cap, floor)
            order = np.argsort(-proba, kind="stable")
            labels = np.zeros(len(feat_rows), dtype=int)
            labels[order[: min(expected, len(feat_rows))]] = 1
            frame["queue_pred"] = labels
        else:
            frame["queue_pred"] = [int(p) for p in preds]
        targets.append(frame)
    if not targets:
        raise RuntimeError("No queue ML rows were generated")
    return pd.concat(targets, ignore_index=True).drop_duplicates(["window_id", "timestamp", "link_id"])


def main() -> None:
    ap = argparse.ArgumentParser(description="Task 2 ML: train pseudo-labeled classifier, predict windows.")
    ap.add_argument("mode", choices=["train", "predict"])
    ap.add_argument("--release-root", type=Path, required=True)
    ap.add_argument("--split", default="validation", help="predict split (predict mode)")
    ap.add_argument("--panel", action="append", help="restrict to panels")
    ap.add_argument("--stride", type=int, default=48)
    ap.add_argument("--max-origins", type=int, default=400)
    ap.add_argument("--eval-before", default=None, help="train origins before YYYY-MM-DD; rest is eval")
    ap.add_argument("--model", type=Path, default=Path("queue_model.pkl"))
    ap.add_argument("--output", type=Path, default=Path("queue_ml.csv"))
    ap.add_argument("--calibrate", action="store_true", help="top-K by probability instead of threshold")
    ap.add_argument("--threshold", type=float, default=0.5, help="decision threshold (ignored with --calibrate)")
    ap.add_argument("--growth-cap", type=float, default=3.0)
    ap.add_argument("--floor", type=int, default=2)
    ap.add_argument("--feature-set", choices=["v1", "v2"], default="v1")
    ap.add_argument("--class-balanced", action="store_true", help="balanced class weights in training")
    args = ap.parse_args()
    read_queue_template, read_window_history, read_window_index, thresholds = _v1()
    from task1.baseline_task1_historical_mean import HERE as _here

    panels_manifest = json.loads((_here / "config" / "corridors.json").read_text(encoding="utf-8"))
    panels = [p["corridor_id"] for p in panels_manifest["panels"]]
    if args.panel:
        panels = [p for p in panels if p in set(args.panel)]
    release = args.release_root.resolve()

    def panel_inputs(panel: str) -> tuple[dict[str, float], dict]:
        panel_dir = release / "corridors" / panel
        links = pd.read_csv(panel_dir / "network" / "links.csv")
        links["link_id"] = links.link_id.astype(str)
        threshold, _ = thresholds(panel_dir, links)
        return threshold, _topology(panel_dir)

    def sample_all(before: str | None, after: str | None) -> tuple[np.ndarray, np.ndarray]:
        parts = [
            sample_training_rows(
                release / "corridors" / panel,
                *panel_inputs(panel),
                args.stride,
                args.max_origins,
                before,
                after,
                feature_set=args.feature_set,
            )
            for panel in panels
        ]
        return np.concatenate([p[0] for p in parts]), np.concatenate([p[1] for p in parts])

    weight = "balanced" if args.class_balanced else None
    if args.mode == "train":
        if args.eval_before:
            X, y = sample_all(args.eval_before, None)
            model = train_classifier(X, y, class_weight=weight)
            Xe, ye = sample_all(None, args.eval_before)
            scores = precision_recall_f1(ye, model.predict(Xe))
            print("eval: " + " ".join(f"{k}={v:.4f}" for k, v in scores.items()), flush=True)
        else:
            X, y = sample_all(None, None)
            model = train_classifier(X, y, class_weight=weight)
        args.model.parent.mkdir(parents=True, exist_ok=True)
        with open(args.model, "wb") as handle:
            pickle.dump(model, handle)
        print(f"Wrote {args.model.resolve()}")
    else:
        with open(args.model, "rb") as model_handle:
            model = pickle.load(model_handle)
        threshold, topology = {}, {}
        for panel in panels:
            threshold[panel], topology[panel] = panel_inputs(panel)
        out = predict_windows(
            model,
            release,
            [args.split],
            threshold,
            topology,
            args.calibrate,
            args.growth_cap,
            args.floor,
            args.threshold,
            args.feature_set,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        out.to_csv(args.output, index=False)
        print(f"Wrote {len(out):,} rows to {args.output.resolve()}")


if __name__ == "__main__":
    main()
