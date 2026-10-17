# Cell-level IoU can invert at the window decision metric
Date: 2026-10-17
Competition: 2026-ieee-big-data-traffic-flow-bench
Finding: Unweighted (class_weight=None) beat balanced on single-model CELL IoU (0.5884 vs 0.5648) but lost badly at window IoU (best 0.4245 vs 0.5310). Unweighted under-predicts queue: its positive rate never clears the truth rate 0.0816 and collapses as threshold rises, killing recall at window granularity. Always confirm a calibration change at the DECISION metric (window IoU), not the cell metric.
Evidence: v44 calsweep kernel: balanced best 0.5310@thr0.40, unweighted best 0.4245@thr0.30; harness matched v43 exactly at 0.35/0.45
Applies when: 
