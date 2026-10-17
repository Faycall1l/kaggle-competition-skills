# When a local metric is saturated, stop tuning against it
Date: 2026-10-17
Competition: 2026-ieee-big-data-traffic-flow-bench
Finding: S_link sat at ~1.0 for both tuned and reference solves, so the whole lambda axis was a no-op. General rule: check the ceiling of any locally-computable proxy before investing — if baseline is already within ~0.001 of the max, the knob cannot move the leaderboard. Redirect effort to components that are NOT saturated (here the LB-only S_od/S_dev/S_attr, or Task1 state).
Evidence: v45: mean S_link_tuned 1.0 vs mean S_link_ref 0.9999 across 10 panels; both at ceiling
Applies when: 
