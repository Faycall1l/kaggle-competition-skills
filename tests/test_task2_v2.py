import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "examples" / "traffic-flow-v2"))

from task2_v2 import forecast_window, load_topology, upstream_hops

TOPO = {
    "A": {"upstream": [], "downstream": ["B"]},
    "B": {"upstream": ["A"], "downstream": ["C"]},
    "C": {"upstream": ["B"], "downstream": []},
}
THRESH = {"A": 60.0, "B": 60.0, "C": 60.0}


def _history(pattern):
    """pattern: dict link -> list of (queued bool, 12 steps). Speed 30 when queued, 100 otherwise."""
    rows = []
    base = pd.Timestamp("2031-03-01T00:00:00Z")
    for link, flags in pattern.items():
        for k, queued in enumerate(flags):
            rows.append(
                {
                    "timestamp": base + pd.Timedelta(minutes=5 * k),
                    "link_id": link,
                    "speed_kmh": 30.0 if queued else 100.0,
                    "is_score_eligible": True,
                }
            )
    return pd.DataFrame(rows)


def _template(links=("A", "B", "C")):
    rows = []
    base = pd.Timestamp("2031-03-01T01:00:00Z")
    for link in links:
        for k in range(6):
            rows.append({"window_id": "w1", "timestamp": base + pd.Timedelta(minutes=5 * k), "link_id": link})
    return pd.DataFrame(rows)


def test_upstream_hops():
    assert upstream_hops(TOPO, "C") == {"C": 0, "B": 1, "A": 2}
    assert upstream_hops(TOPO, "A") == {"A": 0}


def test_load_topology(tmp_path):
    net = tmp_path / "network"
    net.mkdir()
    (net / "lwr_mainline_topology.csv").write_text("link_id,incoming_link_ids,outgoing_link_ids\nB,A,C\n")
    assert load_topology(tmp_path)["B"] == {"upstream": ["A"], "downstream": ["C"]}
    assert load_topology(tmp_path / "missing") == {}


def test_ongoing_persists():
    hist = _history({"A": [True] * 12, "B": [True] * 12, "C": [True] * 12})
    out = forecast_window(hist, _template(), THRESH, TOPO)
    assert out.queue_pred.tolist() == [1] * 18


def test_no_queue_predicts_zero():
    hist = _history({"A": [False] * 12, "B": [False] * 12, "C": [False] * 12})
    out = forecast_window(hist, _template(), THRESH, TOPO)
    assert out.queue_pred.tolist() == [0] * 18


def test_onset_upstream_predicted():
    # Queue arrives at C late in history and grows; B (1 hop upstream) predicted, A (2 hops) within radius.
    hist = _history({"A": [False] * 12, "B": [False] * 12, "C": [False] * 8 + [True] * 4})
    out = forecast_window(hist, _template(), THRESH, TOPO, onset_radius=2)
    by_link = out.groupby("link_id").queue_pred.max().to_dict()
    assert by_link["C"] == 1
    assert by_link["B"] == 1
    assert by_link["A"] == 1


def test_onset_radius_respected():
    hist = _history({"A": [False] * 12, "B": [False] * 12, "C": [False] * 8 + [True] * 4})
    out = forecast_window(hist, _template(), THRESH, TOPO, onset_radius=1)
    by_link = out.groupby("link_id").queue_pred.max().to_dict()
    assert by_link["B"] == 1
    assert by_link["A"] == 0


def test_dissipation_clears_late_steps():
    hist = _history({"A": [True] * 12, "B": [True] * 6 + [False] * 6, "C": [True] * 6 + [False] * 6})
    out = forecast_window(hist, _template(("A",)), THRESH, TOPO)
    assert out.queue_pred.tolist() == [1, 1, 0, 0, 0, 0]
