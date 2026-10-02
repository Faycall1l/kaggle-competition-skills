import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "examples" / "traffic-flow-v2"))

from conserve import load_topology, smooth_frame


def _frame():
    return pd.DataFrame(
        {
            "panel": ["P"] * 6,
            "timestamp": ["2021-01-01T00:00:00Z"] * 6,
            "station_id": ["s"] * 6,
            "link_id": ["A", "B", "C", "A", "B", "C"],
            "mask_regime": ["R1"] * 6,
            "speed_kmh": [100.0] * 6,
            "flow_vph": [1000.0, 100.0, 1000.0, 1000.0, 100.0, 1000.0],
        }
    )


def test_smoothing_pulls_outlier_toward_neighbours():
    topo = {"B": {"upstream": ["A"], "downstream": ["C"]}}
    out = smooth_frame(_frame(), topo, iterations=10, blend=0.5)
    b_vals = out.loc[out.link_id == "B", "flow_vph"].to_numpy()
    assert (b_vals > 100.0).all() and (b_vals < 1000.0).all()


def test_no_neighbours_no_change():
    out = smooth_frame(_frame(), {}, iterations=3)
    assert out.flow_vph.tolist() == [1000.0, 100.0, 1000.0, 1000.0, 100.0, 1000.0]


def test_flows_stay_nonnegative(tmp_path):
    frame = _frame()
    frame.loc[frame.link_id == "A", "flow_vph"] = -5.0
    topo = {"A": {"upstream": ["B"], "downstream": []}, "B": {"upstream": [], "downstream": ["A"]}}
    out = smooth_frame(frame, topo, iterations=2)
    assert (out.flow_vph.to_numpy() >= 0.0).all()


def test_load_topology_missing(tmp_path):
    assert load_topology(tmp_path / "missing") == {}


def test_missing_cell_does_not_blank_neighbours():
    """A NaN cell must not poison its neighbours' smoothed values."""
    frame = _frame()
    frame["timestamp"] = [f"2031-01-01T00:{i:02d}:00Z" for i in range(len(frame))]
    frame.loc[1, "flow_vph"] = np.nan
    topo = {
        "A": {"upstream": [], "downstream": ["B"]},
        "B": {"upstream": ["A"], "downstream": ["C"]},
        "C": {"upstream": ["B"], "downstream": []},
    }
    out = smooth_frame(frame, topo, iterations=3)
    assert np.isnan(out.loc[1, "flow_vph"])
    a_vals = out.loc[out.link_id == "A", "flow_vph"].to_numpy()
    assert (a_vals > 0).all(), "neighbour A was wiped out by the NaN"


def test_large_frame_is_fast():
    """Regression guard: per-cell frame writes made this quadratic."""
    import time

    n_stamps, n_links = 400, 60
    frame = pd.DataFrame(
        {
            "panel": ["P"] * (n_stamps * n_links),
            "timestamp": np.repeat([f"2031-01-{1 + i // 288:02d}T00:00:00Z" for i in range(n_stamps)], n_links),
            "link_id": np.tile([f"L{i}" for i in range(n_links)], n_stamps),
            "flow_vph": np.random.default_rng(0).normal(1000, 100, n_stamps * n_links),
        }
    )
    topo = {
        f"L{i}": {"upstream": [f"L{i-1}"] if i else [], "downstream": [f"L{i+1}"] if i < n_links - 1 else []}
        for i in range(n_links)
    }
    start = time.time()
    smooth_frame(frame, topo, iterations=3)
    elapsed = time.time() - start
    assert elapsed < 5.0, f"smoothing {len(frame)} rows took {elapsed:.1f}s"
