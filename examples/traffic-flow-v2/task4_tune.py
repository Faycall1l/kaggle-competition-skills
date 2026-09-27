"""Task 4 lambda sweep: per-panel regularization tuning against local S_link.

The baseline fixes REG_LAMBDA = 0.05 unexamined. This tuner solves the
non-negative regularized problem over a lambda grid per panel and keeps the
lambda maximizing S_link computed from released counts only:

    S_link = max(0, 1 - sum|A_score f - counts| / sum(counts))

S_link is 25% of Task 4. S_od, S_dev and S_attr need withheld path flows and
are leaderboard-only; a better S_link does not guarantee a better S_ODME, but
a worse one guarantees a worse quarter. Never tune against the reference
solve shipped in the package.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import nnls

import sys as _sys
from pathlib import Path as _Path

# Same bootstrap as the v1 builders: this file ships at src/task4/task4_tune.py,
# so parent.parent is the src/ directory that makes `task4.*` importable.
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))


def _builder():
    """Import builder helpers lazily; the baselines src/ tree is a runtime dependency."""
    try:
        from task4.build_task4_odme_artifacts import load_operator, prior_values, released_counts, released_prior
    except ImportError as exc:
        raise SystemExit(
            "task4_tune needs the baselines src/ tree importable "
            "(https://github.com/jacky850/trafficflowbench-public): " + str(exc)
        )
    return load_operator, prior_values, released_counts, released_prior


def solve_lambda(A: np.ndarray, counts: np.ndarray, base: np.ndarray, reg_lambda: float) -> np.ndarray:
    """Non-negative regularized solve for one lambda value."""
    aa = np.vstack([A, np.sqrt(reg_lambda) * np.eye(A.shape[1])]) if reg_lambda > 0 else A
    bb = np.concatenate([counts, np.sqrt(reg_lambda) * base]) if reg_lambda > 0 else counts
    f, _ = nnls(aa, bb)
    return f


def s_link(A_score: np.ndarray, counts: np.ndarray, f: np.ndarray) -> float:
    """Local S_link of path flows f against released counts."""
    loaded = A_score @ f
    denom = max(float(np.sum(counts)), 1e-9)
    return max(0.0, 1.0 - float(np.sum(np.abs(loaded - counts))) / denom)


def tune_panel(
    path_ids: list[str],
    A: np.ndarray,
    counts: np.ndarray,
    base: np.ndarray,
    scored_idx: list[int],
    lambdas: list[float],
) -> tuple[float, float]:
    """Return (best_lambda, best S_link) over the grid.

    The solve runs on the scored-link subset, matching the builder: unobserved
    connectors carry no measured counts and must not enter the fit.
    """
    A_score = A[scored_idx, :]
    best_lambda, best_score = lambdas[0], -1.0
    for reg_lambda in lambdas:
        score = s_link(A_score, counts, solve_lambda(A_score, counts, base, reg_lambda))
        if score > best_score:
            best_lambda, best_score = reg_lambda, score
    return best_lambda, best_score


def main() -> None:
    load_operator, prior_values, released_counts, released_prior = _builder()
    ap = argparse.ArgumentParser(description="Per-panel lambda sweep for Task 4 ODME.")
    ap.add_argument("--release-root", type=Path, required=True)
    ap.add_argument("--split", choices=["train", "validation", "private"], default="validation")
    ap.add_argument("--output-root", type=Path, required=True)
    ap.add_argument("--panel", action="append", help="tune only selected panel(s)")
    ap.add_argument("--lambdas", default="0,0.01,0.05,0.2,1.0", help="comma-separated grid")
    args = ap.parse_args()
    lambdas = [float(x) for x in args.lambdas.split(",")]
    if not lambdas:
        raise SystemExit("empty lambda grid")
    from task1.baseline_task1_historical_mean import HERE as _here

    panels_manifest = json.loads((_here / "config" / "corridors.json").read_text(encoding="utf-8"))
    panels = [p["corridor_id"] for p in panels_manifest["panels"]]
    if args.panel:
        panels = [p for p in panels if p in set(args.panel)]
    release = args.release_root.resolve()
    args.output_root.mkdir(parents=True, exist_ok=True)
    report = []
    for panel in panels:
        network = release / "corridors" / panel / "network"
        path_ids, link_ids, A, paths = load_operator(network)
        count_frame = released_counts(release, panel, args.split)
        if count_frame is None:
            print(f"[{panel}] no released counts, skipping", flush=True)
            continue
        count_frame["link_id"] = count_frame.link_id.astype(str)
        link_index = {link: i for i, link in enumerate(link_ids)}
        scored = [link for link in count_frame.link_id if link in link_index]
        scored_idx = [link_index[link] for link in scored]
        counts = count_frame.set_index("link_id").reindex(scored)["count"].fillna(0.0).to_numpy(dtype=float)
        base = prior_values(release, panel, args.split, path_ids)
        best_lambda, best_score = tune_panel(path_ids, A, counts, base, scored_idx, lambdas)
        print(f"[{panel}] lambda*={best_lambda} S_link={best_score:.4f}", flush=True)
        report.append({"panel": panel, "lambda": best_lambda, "S_link": best_score})
        f = solve_lambda(A, counts, base, best_lambda)
        frame = paths[["path_id", "origin_zone", "destination_zone"]].copy()
        frame["panel"] = panel
        prior = released_prior(release, panel, args.split)
        frame["departure_time"] = (
            str(prior.departure_time.iloc[0]) if prior is not None and len(prior) else "PUBLIC-TRAIN-PM"
        )
        frame["path_flow"] = f
        frame[["panel", "departure_time", "path_id", "origin_zone", "destination_zone", "path_flow"]].to_csv(
            args.output_root / f"{panel}_tuned_submission.csv", index=False
        )
    pd.DataFrame(report).to_csv(args.output_root / "lambda_report.csv", index=False)
    print(f"Wrote tuned artifacts to {args.output_root.resolve()}")


if __name__ == "__main__":
    main()
