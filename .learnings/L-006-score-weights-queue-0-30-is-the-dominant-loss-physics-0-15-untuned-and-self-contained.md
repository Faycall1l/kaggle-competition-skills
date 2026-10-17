# Score weights: queue (0.30) is the dominant loss, physics (0.15) untuned and self-contained
Date: 2026-10-17
Competition: 2026-ieee-big-data-traffic-flow-bench
Finding: competition_contract.json overall = 0.35*state + 0.30*queue + 0.15*physics + 0.20*odme. Our local: state 0.926 (near ceiling, only 0.026 headroom), queue windowIoU 0.53 (0.141 shortfall = the single biggest loss term), odme S_link saturated, physics never measured. Physics = (1/3)S_FD + (2/3)S_LWR scored ON the submitted state rows and is SELF-CONTAINED (no ground truth needed) so it is locally tunable. Queue-threshold knobs were exhausted (v44) but the queue MODEL (AUPRC 0.68) is the real ceiling, far below what a ~0.924 leader implies (~0.85+). Biggest levers: queue model rewrite (high effort), then physics conserve-param sweep (cheap, 0.15 weight).
Evidence: v32 dev: state macro 0.9266; v43/44: queue windowIoU 0.53; competition_contract.json task_weights state .35 queue .30 physics .15 odme .20, odme formula .45*S_od+.25*S_link+.15*S_dev+.15*S_attr
Applies when: 
