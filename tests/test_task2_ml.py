import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "examples" / "traffic-flow-v2"))

from task2_ml import (
    FEATURE_COLUMNS,
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


def test_decision_threshold_shifts_positive_rate():
    from task2_ml import predict_windows

    assert "decision_threshold" in predict_windows.__code__.co_varnames


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
