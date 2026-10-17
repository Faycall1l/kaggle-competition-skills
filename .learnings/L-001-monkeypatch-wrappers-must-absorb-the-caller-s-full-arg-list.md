# Monkeypatch wrappers must absorb the caller's full arg list
Date: 2026-10-17
Competition: 2026-ieee-big-data-traffic-flow-bench
Finding: Q.bottleneck_frequencies memo wrapper defined as bf(panel_dir, thr) crashes with TypeError when feature_set v2+ calls it as bottleneck_frequencies(panel_dir, threshold, list_files). Define wrappers as def bf(panel_dir, thr, *args, **kwargs) so they match every call site.
Evidence: v44 v6 kernel log: TypeError: bf() takes 2 positional arguments but 3 were given at task2_ml.py:787
Applies when: 
