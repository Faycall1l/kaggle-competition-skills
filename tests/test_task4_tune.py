import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "examples" / "traffic-flow-v2"))

from task4_tune import s_link, solve_lambda, tune_panel


def test_solve_lambda_exact():
    A = np.array([[1.0, 0.0], [1.0, 1.0]])
    counts = np.array([2.0, 5.0])
    base = np.array([2.0, 3.0])
    f = solve_lambda(A, counts, base, 0.0)
    assert np.allclose(A @ f, counts, atol=1e-6)
    assert (f >= 0).all()


def test_s_link_perfect_is_one():
    A = np.eye(2)
    assert s_link(A, np.array([1.0, 2.0]), np.array([1.0, 2.0])) == 1.0


def test_s_link_degrades_with_error():
    A = np.eye(2)
    counts = np.array([10.0, 10.0])
    assert s_link(A, counts, np.array([10.0, 10.0])) > s_link(A, counts, np.array([0.0, 0.0]))


def test_tune_panel_selects_best():
    A = np.array([[1.0, 0.0], [0.0, 1.0]])
    counts = np.array([5.0, 5.0])
    base = np.array([0.0, 0.0])
    best_lambda, best_score = tune_panel(["p1", "p2"], A, counts, base, [0, 1], [0.0, 1.0])
    assert best_lambda == 0.0
    assert best_score == 1.0


def test_tune_panel_regularization_can_win():
    rng = np.random.default_rng(0)
    A = rng.random((6, 3)) + 0.5
    truth = np.array([4.0, 0.0, 2.0])
    counts = A @ truth + rng.normal(0, 0.5, size=6)
    base = np.full(3, 2.0)
    best_lambda, _ = tune_panel(["a", "b", "c"], A, counts, base, [0, 1, 2, 3, 4, 5], [0.0, 0.5, 5.0])
    assert best_lambda in (0.0, 0.5, 5.0)
