# All three cheap knobs exhausted; only the queue MODEL has real headroom
Date: 2026-10-17
Competition: 2026-ieee-big-data-traffic-flow-bench
Finding: After v44-v46 every locally-tunable cheap lever is proven dead: queue decision threshold (flat 0.35-0.45), ODME lambda (S_link saturated 1.0, lambda*=0 all panels), physics S_FD (0.986). The remaining loss budget is dominated by the queue MODEL itself: 0.30 weight at 0.53 windowIoU (AUPRC 0.68) vs a leader's implied ~0.85+. That is ~0.14 of overall — an order of magnitude more than all cheap knobs combined. Next real work = rebuild the queue model (spatiotemporal/propagation features, better pseudo-labels), which is high-effort and high-reward, not a knob sweep.
Evidence: v44 queue thr flat; v45 ODME lambda saturated; v46 S_FD 0.986; contract weights state .35 queue .30 physics .15 odme .20; v43 queue windowIoU 0.53
Applies when: 
