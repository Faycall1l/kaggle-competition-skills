"""Conservation smoothing for reconstructed link flows.

Independent per-cell predictions violate vehicle conservation between
neighbouring links. This pass diffuses each link's predicted flow toward its
topological neighbours' mean, blended 50/50 with the original value, for a
few iterations. Smoothing reduces spatial noise (small RMSE win) and improves
the LWR conservation component of the physics score, which dominates it.

Speeds are untouched: only flows enter conservation. Links without neighbours
keep their values. Writes a new file; never mutates the input.

The diffusion is a sparse matrix product over a dense (timestamp x link)
grid, so cost is linear in cells rather than quadratic like per-cell frame
writes.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse


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


def _adjacency(links: list[str], neighbours: dict[str, dict[str, list[str]]]) -> sparse.csr_matrix:
    """Symmetric adjacency matrix over `links` (1 where two links are neighbours)."""
    index = {link: i for i, link in enumerate(links)}
    rows: list[int] = []
    cols: list[int] = []
    for link, sides in neighbours.items():
        if link not in index:
            continue
        for other in sides.get("upstream", []) + sides.get("downstream", []):
            if other not in index or other == link:
                continue
            rows.append(index[link])
            cols.append(index[other])
    return sparse.coo_matrix((np.ones(len(rows)), (rows, cols)), shape=(len(links), len(links))).tocsr()


def smooth_frame(
    frame: pd.DataFrame, neighbours: dict[str, dict[str, list[str]]], iterations: int = 3, blend: float = 0.5
) -> pd.DataFrame:
    """Diffuse flow_vph toward neighbour means, per timestamp. Returns a copy."""
    frame = frame.copy()
    frame["link_id"] = frame.link_id.astype(str)
    links = sorted(set(frame.link_id))
    matrix = _adjacency(links, neighbours)
    if matrix.nnz == 0:
        return frame
    index = {link: i for i, link in enumerate(links)}
    codes = frame.link_id.map(index).to_numpy()
    stamps = pd.factorize(frame.timestamp, sort=False)[0]
    n_stamps = int(stamps.max()) + 1 if len(stamps) else 0
    grid = np.full((n_stamps, len(links)), np.nan)
    grid[stamps, codes] = frame.flow_vph.to_numpy(dtype=float)
    present = ~np.isnan(grid)
    filled = np.where(present, grid, 0.0)
    present_f = present.astype(float)
    for _ in range(iterations):
        neighbour_sum = filled @ matrix.T
        neighbour_count = present_f @ matrix.T
        with np.errstate(invalid="ignore", divide="ignore"):
            neighbour_mean = np.where(neighbour_count > 0, neighbour_sum / neighbour_count, grid)
        updated = (1.0 - blend) * grid + blend * neighbour_mean
        # cells with no observed neighbours keep their own value
        grid = np.where(neighbour_count > 0, updated, grid)
    frame["flow_vph"] = np.clip(grid[stamps, codes], 0.0, None)
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
