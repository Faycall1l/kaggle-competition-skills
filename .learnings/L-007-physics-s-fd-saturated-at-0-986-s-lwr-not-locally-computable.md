# Physics S_FD saturated at 0.986; S_LWR not locally computable
Date: 2026-10-17
Competition: 2026-ieee-big-data-traffic-flow-bench
Finding: Champion state_submission S_FD on validation submitted cells = 0.9859 macro (min panel 0.9805, max 0.9915), empty_share 0 everywhere (no empty-road forfeit). This is a LOWER bound — scored S_FD includes on-FD truth cells, so it is even higher. Headroom to 1.0 is ~0.014 on S_FD -> /3 -> x0.15 weight = ~0.0007 overall: negligible. S_LWR (2/3 of S_physics) is NOT locally computable — organizer boundary flux is unpublished and topology-derived flux puts even exact truth at S_LWR 0.0 (score_task3 docstring). So the physics task (0.15 weight) is effectively closed for offline tuning; only S_FD exists and it is saturated. Independent GBM speed/flow predictions already land on the FD triangle.
Evidence: v46 sfd kernel: S_FD macro 0.9859 across 10 panels x 3 regimes; contract S_physics=(S_FD+2S_LWR)/3, task weight physics 0.15
Applies when: 
