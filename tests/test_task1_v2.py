import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "examples" / "traffic-flow-v2"))

from task1_v2 import eligible, free_speed_by_link, load_topology, temporal_fill


def test_temporal_fill_interpolates():
    values = np.array([10.0, np.nan, 30.0, np.nan, np.nan])
    valid = np.array([True, False, True, False, False])
    filled = temporal_fill(values, valid, half_window=6)
    assert filled[1] == 20.0
    assert np.isnan(filled[3]) or filled[3] == 30.0
    assert filled[0] == 10.0


def test_temporal_fill_window_respected():
    values = np.array([10.0, np.nan, np.nan, np.nan, 50.0])
    valid = np.array([True, False, False, False, True])
    assert np.isnan(temporal_fill(values, valid, half_window=1)[2])
    assert temporal_fill(values, valid, half_window=6)[2] == 30.0


def test_temporal_fill_empty():
    assert np.isnan(temporal_fill(np.array([np.nan]), np.array([False]))).all()


def test_load_topology(tmp_path):
    net = tmp_path / "network"
    net.mkdir()
    (net / "lwr_mainline_topology.csv").write_text("link_id,incoming_link_ids,outgoing_link_ids\nA,,B\nB,A,C\nC,B,\n")
    topo = load_topology(tmp_path)
    assert topo["B"] == {"upstream": ["A"], "downstream": ["C"]}
    assert load_topology(tmp_path / "missing") == {}


def test_free_speed_clamp_source(tmp_path):
    net = tmp_path / "network"
    net.mkdir()
    (net / "links.csv").write_text("link_id,lanes,free_speed_kmh\nA,3,100.0\nB,2,0\n")
    speeds = free_speed_by_link(tmp_path)
    assert speeds == {"A": 100.0}
    assert free_speed_by_link(tmp_path / "missing") == {}


def test_eligible_contract(tmp_path):
    frame = pd.DataFrame(
        {
            "pct_observed": [100, 50, 100],
            "speed_kmh": [60.0, 60.0, float("nan")],
            "flow_vph": [1000.0, 1000.0, 1000.0],
        }
    )
    assert eligible(frame).tolist() == [True, False, False]
