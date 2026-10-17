# Queue decision threshold 0.35 is already optimal
Date: 2026-10-17
Competition: 2026-ieee-big-data-traffic-flow-bench
Finding: Balanced condition-split queue model is flat thr 0.35-0.45 (windowIoU 0.5303/0.5310/0.5308); current champion thr 0.35 floor 4 is at local optimum. Moving to 0.40 buys +0.0007 — not worth a submission slot. Floor (2/4/6) is irrelevant (v43). Queue-threshold knob is exhausted; next gains must come from Task1 state or Task4 ODME.
Evidence: v43 qwin + v44 calsweep kernels; ablation: queue contributes ~0.20, odme ~0.23 over ~0.55 state base
Applies when: 
