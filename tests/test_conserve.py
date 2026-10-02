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


def test_fd_parameters_recomputes_kcrit(tmp_path):
    """fd_parameters.csv is authoritative; k_crit is capacity/free_speed, not averaged."""
    from conserve import load_fd_parameters

    net = tmp_path / "network"
    net.mkdir(parents=True)
    pd.DataFrame(
        {
            "link_id": ["A", "A", "B"],
            "free_speed_kmh": [110.0, 120.0, 100.0],
            "capacity_vph": [6000.0, 6000.0, 5000.0],
            "lanes": [4.0, 4.0, 3.0],
        }
    ).to_csv(net / "fd_parameters.csv", index=False)
    params = load_fd_parameters(tmp_path)
    v_free, capacity, k_crit, k_jam = params["A"]
    assert v_free == 115.0, "free_speed averages over stations sharing the link"
    assert k_crit == capacity / v_free, "k_crit recomputed, not averaged"
    assert k_jam >= k_crit * 1.05
    assert load_fd_parameters(tmp_path / "nope") == {}


def test_fd_flow_zeroes_the_scorer_residual():
    """The projection target must make S_FD's own residual vanish."""
    from conserve import fd_flow

    def scorer_resid(v, q, v_free, cap, k_crit, k_jam, lanes):
        q_lane, k_lane = q / lanes, (q / max(v, 1e-9)) / lanes
        c_l, k_l, j_l = cap / lanes, k_crit / lanes, k_jam / lanes
        fd = v_free * k_lane if k_lane <= k_l else (c_l / max(j_l - k_l, 1e-9)) * max(j_l - k_lane, 0.0)
        return q_lane - fd

    for v_free, cap, k_crit, k_jam, lanes in [
        (100.0, 6000.0, 60.0, 120.0, 1.0),
        (100.0, 8000.0, 80.0, 160.0, 4.0),
    ]:
        for v in (80.0, 60.0, 40.0, 20.0):
            q = fd_flow(np.array([v]), v_free, cap, k_crit, k_jam, lanes)[0]
            assert abs(scorer_resid(v, q, v_free, cap, k_crit, k_jam, lanes)) < 1e-6


def test_fd_flow_empty_road_at_free_speed():
    from conserve import fd_flow

    assert fd_flow(np.array([100.0]), 100.0, 6000.0, 60.0, 120.0)[0] == 0.0


def test_fd_projection_pulls_flow_toward_diagram():
    from conserve import project_onto_fd

    frame = _frame()
    frame["speed_kmh"] = 50.0
    from conserve import fd_flow

    params = {"A": (100.0, 6000.0, 60.0, 120.0), "B": (100.0, 6000.0, 60.0, 120.0), "C": (100.0, 6000.0, 60.0, 120.0)}
    out = project_onto_fd(frame, params, alpha=0.15)
    a = out.loc[out.link_id == "A", "flow_vph"].to_numpy()
    target = fd_flow(np.array([50.0]), 100.0, 6000.0, 60.0, 120.0)[0]
    assert target > 1000.0
    assert (a > 1000.0).all()
    assert abs(a[0] - (0.85 * 1000.0 + 0.15 * target)) < 1e-6


def test_fd_projection_is_a_noop_when_disabled():
    from conserve import project_onto_fd

    frame = _frame()
    assert project_onto_fd(frame, {"A": (100.0, 6000.0, 60.0, 120.0)}, alpha=0.0).equals(frame)
