import inspect
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "examples" / "traffic-flow-v2"))

from task2_ml import (
    FEATURE_COLUMNS,
    FEATURE_COLUMNS_V2,
    label_horizon,
    precision_recall_f1,
    row_features,
    slope_of,
    train_classifier,
    upstream_distances,
)


def test_feature_vector_length():
    vec = row_features(np.array([100.0] * 12), np.ones(12, dtype=bool), 0.5, 2, 60.0, 100, 3)
    assert len(vec) == len(FEATURE_COLUMNS) == 10


def test_slope_of():
    assert slope_of(np.array([100.0, 90.0, 80.0])) < -9.0
    assert abs(slope_of(np.array([100.0, 100.0, 100.0]))) < 1e-9
    assert slope_of(np.array([np.nan])) == 0.0


def test_label_horizon_threshold_rule():
    speeds = np.array([100.0, 50.0, 40.0])
    eligible = np.array([True, True, False])
    assert label_horizon(speeds, eligible, 60.0).tolist() == [0, 1, 0]
    assert label_horizon(speeds, eligible, 60.0, mode="sustained").tolist() == [0, 0, 0]


def test_label_horizon_sustained_drops_flicker_keeps_runs():
    eligible = np.array([True, True, True])
    flicker = np.array([100.0, 50.0, 100.0])
    assert label_horizon(flicker, eligible, 60.0).tolist() == [0, 1, 0]
    assert label_horizon(flicker, eligible, 60.0, mode="sustained").tolist() == [0, 0, 0]
    run = np.array([100.0, 50.0, 40.0])
    assert label_horizon(run, eligible, 60.0, mode="sustained").tolist() == [0, 0, 1]


def test_upstream_distances():
    topo = {"A": {"upstream": [], "downstream": ["B"]}, "B": {"upstream": ["A"], "downstream": []}}
    assert upstream_distances(topo, {"B"}) == {"B": 0, "A": 1}
    assert upstream_distances(topo, set()) == {}


def test_precision_recall_f1():
    scores = precision_recall_f1(np.array([1, 1, 0, 0]), np.array([1, 0, 1, 0]))
    assert scores == {"precision": 0.5, "recall": 0.5, "f1": 0.5, "positive_rate": 0.5}


def test_train_classifier_separable():
    rng = np.random.default_rng(0)
    X = np.vstack([rng.normal(0, 1, (50, 10)), rng.normal(5, 1, (50, 10))])
    y = np.array([0] * 50 + [1] * 50)
    model = train_classifier(X, y)
    assert (model.predict(X) == y).mean() > 0.95


def test_train_classifier_balanced():
    rng = np.random.default_rng(1)
    X = np.vstack([rng.normal(0, 1, (90, 10)), rng.normal(5, 1, (10, 10))])
    y = np.array([0] * 90 + [1] * 10)
    model = train_classifier(X, y, class_weight="balanced")
    assert (model.predict(X[90:]) == 1).mean() > 0.5


def test_model_payload_records_feature_set(tmp_path):
    """The pickle carries its feature set so predict can refuse a mismatched run."""
    rng = np.random.default_rng(2)
    X = np.vstack([rng.normal(0, 1, (40, 10)), rng.normal(4, 1, (40, 10))])
    y = np.array([0] * 40 + [1] * 40)
    model = train_classifier(X, y)
    path = tmp_path / "m.pkl"
    with open(path, "wb") as handle:
        pickle.dump({"model": model, "feature_set": "v1"}, handle)
    with open(path, "rb") as handle:
        payload = pickle.load(handle)
    assert payload["feature_set"] == "v1"
    assert payload["model"].n_features_in_ == 10
    # a v2 run builds 21 columns, so the guard must trip for a 10-feature model
    run_width = len(FEATURE_COLUMNS_V2)
    assert payload["model"].n_features_in_ != run_width


def test_bottleneck_frequencies(tmp_path):
    import pandas as pd

    from task2_ml import bottleneck_frequencies

    train = tmp_path / "train" / "mainline_states"
    train.mkdir(parents=True)
    base = pd.Timestamp("2030-06-01T00:00:00Z")
    rows = []
    for k in range(20):
        rows.append(
            {
                "timestamp": (base + pd.Timedelta(minutes=5 * k)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "link_id": "A",
                "speed_kmh": 30.0 if k % 2 == 0 else 100.0,
                "is_score_eligible": True,
            }
        )
        rows.append(
            {
                "timestamp": (base + pd.Timedelta(minutes=5 * k)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "link_id": "B",
                "speed_kmh": 100.0,
                "is_score_eligible": True,
            }
        )
    pd.DataFrame(rows).to_parquet(train / "day.parquet")
    lister = lambda panel_dir, split: sorted((panel_dir / split / "mainline_states").glob("**/*.parquet"))
    freq = bottleneck_frequencies(tmp_path, {"A": 60.0, "B": 60.0}, lister)
    assert freq == {"A": 0.5, "B": 0.0}
    assert bottleneck_frequencies(tmp_path / "missing", {}, lister) == {}


def test_decision_threshold_shifts_positive_rate():
    from task2_ml import predict_windows

    assert "decision_threshold" in predict_windows.__code__.co_varnames


def test_onset_rule_zeros_early_steps_only_for_onset_windows():
    """Organizer rule: in queue_onset windows the queue can only be at T+30."""
    from task2_ml import apply_queue_window_rules

    horizon = [pd.Timestamp(f"2026-01-01 07:{m:02d}", tz="UTC") for m in (5, 10, 15, 20, 25, 30)]
    labels = np.ones(len(horizon) * 2, dtype=int)
    proba = np.full(len(horizon) * 2, 0.4)
    stamps = np.repeat(np.array(horizon, dtype=object), 2)

    onset = apply_queue_window_rules(labels, proba, stamps, "queue_onset", horizon, True, False)
    assert set(np.unique(onset)) == {0, 1}
    assert onset[stamps == horizon[-1]].all()
    assert onset[stamps != horizon[-1]].sum() == 0

    ongoing = apply_queue_window_rules(labels, proba, stamps, "queue_ongoing", horizon, True, False)
    assert ongoing.sum() == len(labels)


def test_onset_rule_off_leaves_every_step_alone():
    from task2_ml import apply_queue_window_rules

    horizon = [pd.Timestamp(f"2026-01-01 07:{m:02d}", tz="UTC") for m in (5, 30)]
    labels = np.ones(2, dtype=int)
    stamps = np.array(horizon, dtype=object)
    out = apply_queue_window_rules(labels, np.array([0.9, 0.1]), stamps, "queue_onset", horizon, False, False)
    assert out.tolist() == [1, 1]


def test_empty_window_is_promoted_because_every_horizon_has_a_queue():
    """requires_queue_in_horizon: true, so an all-zero window is a guaranteed 0."""
    from task2_ml import apply_queue_window_rules

    horizon = [pd.Timestamp("2026-01-01 07:30", tz="UTC")]
    proba = np.array([0.1, 0.7, 0.3])
    stamps = np.repeat(np.array(horizon, dtype=object), 3)

    out = apply_queue_window_rules(np.zeros(3, dtype=int), proba, stamps, "queue_ongoing", horizon, True, True)
    assert out.tolist() == [0, 1, 0]

    allowed = apply_queue_window_rules(np.zeros(3, dtype=int), proba, stamps, "queue_ongoing", horizon, True, False)
    assert allowed.sum() == 0


def test_promotion_in_onset_window_lands_on_the_final_step():
    from task2_ml import apply_queue_window_rules

    horizon = [pd.Timestamp(f"2026-01-01 07:{m:02d}", tz="UTC") for m in (5, 30)]
    # Highest probability sits on the early step, which the onset rule forbids.
    proba = np.array([0.9, 0.4, 0.8, 0.2])
    stamps = np.array([horizon[0], horizon[0], horizon[1], horizon[1]], dtype=object)

    out = apply_queue_window_rules(np.zeros(4, dtype=int), proba, stamps, "queue_onset", horizon, True, True)
    assert out.tolist() == [0, 0, 1, 0]


def test_expected_positives_growth():
    import pandas as pd

    from task2_ml import expected_positives

    rows = []
    for step in range(12):
        for link, queued in (("A", step >= 10), ("B", step >= 4)):
            rows.append(
                {"step": step, "link_id": link, "speed_kmh": 30.0 if queued else 100.0, "is_score_eligible": True}
            )
    hist = pd.DataFrame(rows)
    assert expected_positives(hist, {"A": 60.0, "B": 60.0}, 3.0, 2) >= 2


def test_expected_positives_floor():
    import pandas as pd

    from task2_ml import expected_positives

    rows = [{"step": s, "link_id": "A", "speed_kmh": 100.0, "is_score_eligible": True} for s in range(12)]
    hist = pd.DataFrame(rows)
    assert expected_positives(hist, {"A": 60.0}, 3.0, 2) == 2


def test_definitions_precede_first_use():
    """Regression: predict_windows must be defined before main() runs.

    Import-based tests bind every def and cannot catch use-before-def at
    script execution. Parse the file and enforce ordering instead.
    """
    import ast

    path = Path(__file__).resolve().parent.parent / "examples" / "traffic-flow-v2" / "task2_ml.py"
    tree = ast.parse(path.read_text())
    order = [node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    assert "predict_windows" in order and "main" in order
    assert order.index("predict_windows") < order.index("main")


def _fixture_panel(tmp_path):
    train = tmp_path / "train" / "mainline_states"
    train.mkdir(parents=True)
    base = pd.Timestamp("2030-06-01T00:00:00Z")
    rows = []
    for link in ("A", "B"):
        for k in range(60):
            queued = link == "B" and 30 <= k < 42
            rows.append(
                {
                    "timestamp": (base + pd.Timedelta(minutes=5 * k)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "link_id": link,
                    "speed_kmh": 30.0 if queued else 100.0,
                    "is_score_eligible": True,
                }
            )
    pd.DataFrame(rows).to_parquet(train / "day.parquet")
    return tmp_path


def test_sample_before_after_split(tmp_path):
    from task2_ml import sample_training_rows

    panel = _fixture_panel(tmp_path)
    topo = {"A": {"upstream": [], "downstream": ["B"]}, "B": {"upstream": ["A"], "downstream": []}}
    thresh = {"A": 60.0, "B": 60.0}
    lister = lambda panel_dir, split: sorted((panel_dir / split / "mainline_states").glob("**/*.parquet"))
    X_all, y_all = sample_training_rows(panel, thresh, topo, stride=6, max_origins=50, list_files=lister)
    assert len(X_all) > 0 and X_all.shape[1] == 10
    assert set(y_all.tolist()) == {0, 1}
    X_early, _ = sample_training_rows(
        panel, thresh, topo, stride=6, max_origins=50, before="2030-06-01T02:00:00", list_files=lister
    )
    assert 0 < len(X_early) < len(X_all)
    X_late, _ = sample_training_rows(
        panel, thresh, topo, stride=6, max_origins=50, after="2030-06-01T02:00:00", list_files=lister
    )
    assert len(X_late) > 0


def _fixture_panel_v2(tmp_path):
    train = tmp_path / "train" / "mainline_states"
    train.mkdir(parents=True)
    base = pd.Timestamp("2030-06-01T00:00:00Z")
    rows = []
    for link in ("A", "B"):
        for k in range(60):
            queued = link == "B" and 30 <= k < 42
            rows.append(
                {
                    "timestamp": (base + pd.Timedelta(minutes=5 * k)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "link_id": link,
                    "speed_kmh": 30.0 if queued else 100.0,
                    "flow_vph": 500.0 if queued else 2000.0,
                    "occupancy": 25.0 if queued else 8.0,
                    "is_score_eligible": True,
                }
            )
    pd.DataFrame(rows).to_parquet(train / "day.parquet")
    return tmp_path


def test_sample_v2_width_and_channels(tmp_path):
    from task2_ml import sample_training_rows

    panel = _fixture_panel_v2(tmp_path)
    topo = {"A": {"upstream": [], "downstream": ["B"]}, "B": {"upstream": ["A"], "downstream": []}}
    thresh = {"A": 60.0, "B": 60.0}
    lister = lambda panel_dir, split: sorted((panel_dir / split / "mainline_states").glob("**/*.parquet"))
    X, y = sample_training_rows(panel, thresh, topo, stride=6, max_origins=50, list_files=lister, feature_set="v2")
    assert X.shape[1] == len(FEATURE_COLUMNS_V2) == 21
    assert set(y.tolist()) == {0, 1}
    flow_idx = FEATURE_COLUMNS_V2.index("mean_flow")
    assert X[:, flow_idx].max() > 1000.0
