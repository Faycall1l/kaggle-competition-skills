"""Conservation smoothing for reconstructed link flows.

Independent per-cell predictions violate vehicle conservation between
neighbouring links. This pass diffuses each link's predicted flow toward its
topological neighbours' mean, blended 50/50 with the original value, for a
few iterations. Smoothing reduces spatial noise (small RMSE win) and improves
the LWR conservation component of the physics score, which dominates it.

Speeds are untouched: only flows enter conservation. Links without neighbours
keep their values. Operates on a state submission file in place (writes a new
file, never mutates the input).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def load_topology(panel_dir: Path) -> dict[str, dict[str, list[str]]]:
    """Map link_id -> {upstream, downstream} from lwr_mainline_topology.csv."""
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


def smooth_frame(
    frame: pd.DataFrame, neighbours: dict[str, dict[str, list[str]]], iterations: int = 3, blend: float = 0.5
) -> pd.DataFrame:
    """Diffuse flow_vph toward neighbour means, per timestamp. Returns a copy."""
    frame = frame.copy()
    frame["link_id"] = frame.link_id.astype(str)
    for _ in range(iterations):
        updates: dict[int, float] = {}
        for stamp, group in frame.groupby("timestamp", sort=False):
            values = dict(zip(group.link_id.astype(str), group.flow_vph.astype(float)))
            for pos, link in zip(group.index, group.link_id.astype(str)):
                pool = neighbours.get(link, {}).get("upstream", []) + neighbours.get(link, {}).get("downstream", [])
                known = [values[other] for other in pool if other in values and np.isfinite(values[other])]
                if known:
                    updates[pos] = (1.0 - blend) * values[link] + blend * float(np.mean(known))
        for pos, value in updates.items():
            frame.at[pos, "flow_vph"] = max(value, 0.0)
    return frame


def main() -> None:
    ap = argparse.ArgumentParser(description="Conservation smoothing for state submission flows.")
    ap.add_argument("--input", type=Path, required=True, help="state submission CSV")
    ap.add_argument("--network-root", type=Path, required=True, help="release corridors/ directory")
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--iterations", type=int, default=3)
    ap.add_argument("--blend", type=float, default=0.5)
    args = ap.parse_args()
    frame = pd.read_csv(args.input)
    parts = []
    for panel, group in frame.groupby("panel", sort=False):
        topology = load_topology(args.network_root / str(panel))
        parts.append(smooth_frame(group, topology, args.iterations, args.blend))
    out = pd.concat(parts, ignore_index=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output, index=False)
    print(f"Wrote {len(out):,} rows to {args.output.resolve()}")


if __name__ == "__main__":
    main()
