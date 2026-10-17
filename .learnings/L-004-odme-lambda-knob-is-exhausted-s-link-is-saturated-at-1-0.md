# ODME lambda knob is exhausted; S_link is saturated at 1.0
Date: 2026-10-17
Competition: 2026-ieee-big-data-traffic-flow-bench
Finding: Per-panel lambda sweep (0/0.01/0.05/0.2/1.0) picked lambda*=0.0 for ALL 10 panels — pure unregularized NNLS, no prior. S_link_tuned 1.0000 vs released reference 0.9999 (delta +0.0001, all 10 panels 'improved' but by rounding). S_link is already saturated at its ceiling; there is no headroom, and the champion's reference solve is locally optimal. Do not tune lambda against S_link. The prior (lambda>0) only ever hurts S_link — it exists for the LB-only Task4 components (S_od/S_dev/S_attr, the other 75%), which cannot be measured offline.
Evidence: v45 odmelam kernel v5: lambda*=0.0 for 10/10 panels; SCORE ref overall S_link=0.9999, tuned overall S_link=1.0; delta +0.0001
Applies when: 
