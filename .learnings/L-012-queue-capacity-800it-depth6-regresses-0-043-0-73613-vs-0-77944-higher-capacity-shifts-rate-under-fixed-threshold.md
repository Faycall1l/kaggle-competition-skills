# Queue capacity 800it/depth6 regresses -0.043 (0.73613 vs 0.77944): higher capacity shifts rate under fixed threshold
Date: 2026-10-19
Competition: 2026-ieee-big-data-traffic-flow-bench
Finding: v49 blind submission (champion state+odme+threshold 0.35, only queue model capacity changed 400it/depth5/lr0.05 -> 800it/depth6/lr0.04) scored 0.73613, a -0.043 regression vs champion v32b 0.77944. The higher-capacity model produced pos_rate 0.0687 (val) vs champion ~0.10; under the FIXED 0.35 cut, fewer positives means lower recall and v44 already established fewer positives lowers windowIoU. So capacity hurt through the calibrated-rate channel, not because ranking is worse. Combined with v44 (flat threshold optimal) and v48 (calibrate top-K under-predicts 10x), the queue model is exhausted across decision-rule AND capacity axes; champion v32b 0.77944 stands as best.
Evidence: v49 ref 57390445 public 0.73613 vs v32b 0.77944; v49 log pos_rate 0.0700 val / 0.0674 priv; v44 threshold sweep flat 0.5303-0.5310 for 0.35-0.45 then declines; v48 calibrate pos_rate 0.0096
Applies when: 
