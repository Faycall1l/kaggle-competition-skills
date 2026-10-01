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
