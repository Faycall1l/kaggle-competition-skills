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


def train_classifier(X: np.ndarray, y: np.ndarray):  # type: ignore[no-untyped-def]
    """Gradient boosting on the feature matrix. Returns the fitted model."""
    from sklearn.ensemble import HistGradientBoostingClassifier

    model = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.1, max_depth=5, random_state=0)
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


def sample_training_rows(
    panel_dir: Path,
    threshold: dict[str, float],
    topology: dict[str, dict[str, list[str]]],
    stride: int = 48,
    max_origins: int = 400,
    before: str | None = None,
    after: str | None = None,
    list_files=None,  # type: ignore[no-untyped-def]
) -> tuple[np.ndarray, np.ndarray]:
    """Sample (features, labels) from unmasked train observations.

    Origins stride through time deterministically; labels are the threshold
    rule on the following 6 steps. `before`/`after` (YYYY-MM-DD) restrict
    origins for time-split evaluation. Panel-agnostic: no link or panel ids
    leak into features, so one global model serves all panels. `list_files`
    overrides the release file lookup (fixture tests).
    """
    if list_files is None:
        from task1.baseline_task1_historical_mean import files as _train_files

        list_files = _train_files

    frames = []
    for path in list_files(panel_dir, "train"):
        frames.append(pd.read_parquet(path, columns=["timestamp", "link_id", "speed_kmh", "is_score_eligible"]))
    if not frames:
        return np.zeros((0, len(FEATURE_COLUMNS))), np.zeros(0, dtype=int)
    frame = pd.concat(frames, ignore_index=True)
    frame["link_id"] = frame.link_id.astype(str)
    frame["timestamp"] = pd.to_datetime(frame.timestamp, utc=True)
    frame = frame.sort_values(["link_id", "timestamp"])
    frame["speed"] = pd.to_numeric(frame.speed_kmh, errors="coerce")
    frame["eligible"] = frame.is_score_eligible.astype(bool)

    def _window_arrays(group: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
        speeds = group.speed.to_numpy()
        eligible = group.eligible.to_numpy(dtype=bool)
        times = pd.DatetimeIndex(group.timestamp).tz_convert(None).to_numpy()
        if before is not None:
            keep = times < np.datetime64(before)
            speeds, eligible, times = speeds[keep], eligible[keep], times[keep]
        if after is not None:
            keep = times >= np.datetime64(after)
            speeds, eligible, times = speeds[keep], eligible[keep], times[keep]
        if len(speeds) < HISTORY_STEPS + HORIZON_STEPS:
            return None
        return speeds, eligible, times

    series: dict[str, pd.DataFrame] = {link: group for link, group in frame.groupby("link_id", sort=False)}
    filtered: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    for link, group in series.items():
        arrays = _window_arrays(group)
        if arrays is not None:
            filtered[str(link)] = arrays
    # Note: neighbor lookup aligns by position, assuming the shared 5-minute
    # calendar (missing reports are NaN rows, not missing rows).
    X_rows: list[list[float]] = []
    y_rows: list[int] = []
    for link, (speeds, eligible, times) in filtered.items():
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
            for k in range(HORIZON_STEPS):
                X_rows.append(row_features(hist_speeds, hist_elig, near_frac, near_hops, limit, tod_slot, k))
                y_rows.append(int(labels[k]))
    X = np.array(X_rows, dtype=float)
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
                release / "corridors" / panel, *panel_inputs(panel), args.stride, args.max_origins, before, after
            )
            for panel in panels
        ]
        return np.concatenate([p[0] for p in parts]), np.concatenate([p[1] for p in parts])

    if args.mode == "train":
        if args.eval_before:
            X, y = sample_all(args.eval_before, None)
            model = train_classifier(X, y)
            Xe, ye = sample_all(None, args.eval_before)
            scores = precision_recall_f1(ye, model.predict(Xe))
            print("eval: " + " ".join(f"{k}={v:.4f}" for k, v in scores.items()), flush=True)
        else:
            X, y = sample_all(None, None)
            model = train_classifier(X, y)
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
        out = predict_windows(model, release, [args.split], threshold, topology)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        out.to_csv(args.output, index=False)
        print(f"Wrote {len(out):,} rows to {args.output.resolve()}")


if __name__ == "__main__":
    main()


def predict_windows(
    model,  # type: ignore[no-untyped-def]
    root: Path,
    splits: list[str],
    threshold: dict[str, dict[str, float]],
    topology: dict[str, dict],
) -> pd.DataFrame:
    """Predict queue_pred for released windows. Returns v1-compatible rows."""
    from task2.build_task2_persistence_submission import read_queue_template

    _, read_window_history, read_window_index, _ = _v1()
    windows = read_window_index(root, splits)
    history = read_window_history(root, splits)
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
            else:
                g = g.sort_values("step").tail(HISTORY_STEPS)
                speeds = pd.to_numeric(g.speed_kmh, errors="coerce").to_numpy(dtype=float)
                elig = g.is_score_eligible.astype(bool).to_numpy(dtype=bool)
                pad = HISTORY_STEPS - len(speeds)
                if pad > 0:
                    speeds = np.concatenate([np.full(pad, np.nan), speeds])
                    elig = np.concatenate([np.zeros(pad, dtype=bool), elig])
            states = []
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
            near_frac = float(sum(states) / len(states)) if states else 0.0
            limit = threshold[panel].get(link, 63.0)
            stamp = row.timestamp
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
        preds = model.predict(np.array(feat_rows, dtype=float))
        frame = pd.DataFrame(meta_rows, columns=["window_id", "timestamp", "link_id"])
        frame["queue_pred"] = [int(p) for p in preds]
        targets.append(frame)
    if not targets:
        raise RuntimeError("No queue ML rows were generated")
    return pd.concat(targets, ignore_index=True).drop_duplicates(["window_id", "timestamp", "link_id"])
