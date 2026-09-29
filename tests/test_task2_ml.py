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
