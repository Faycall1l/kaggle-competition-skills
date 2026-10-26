# Training-mask augmentation is neutral: the imputer's scored-month plateau is the model class, not the mask distribution

Date: 2026-10-26
Competition: 2026-ieee-big-data-traffic-flow-bench
Finding: The shipped imputer's weakest regime on the scored month is R3 — the 50%-blanked one, where runs are longest — and there it merely ties the temporal-neighbour rule (D12_I5_N R3: model 0.9174 vs rule 0.9191) while gaining +0.02..+0.03 on R1. The obvious hypothesis is that it is trained on release masks whose median run is one step and therefore never practises extrapolation. It is wrong: teaching it exactly that distribution is worth +0.0013 S_state, inside the noise.

Paired experiment (same test masks, same seed stream; only the *training* masks differ), all eight panels, 2031-03 real observed cells, +20% blanks on the test side:

| variant | rule | model | edge |
|---|---|---|---|
| shipped fit recipe | 0.8990 | 0.9084 | +0.0094 |
| fit on masks with +20% longer runs | 0.8990 | 0.9097 | +0.0107 |

Per-panel change in the edge: D12_I5_N +0.004, D12_I5_S +0.005, D7_I10_E +0.001, D7_I10_W -0.002, D7_I210_E -0.001, D7_I210_W 0.000, D7_I405_N +0.003, D7_I405_S 0.000 — five up, two down, one flat. At the effective state weight (0.51) that is +0.0007 on the leaderboard, i.e. not worth a slot.

Design note that cost a run: the first attempt consumed the same RNG stream for the augmentation and for the test masks, which changed *which* cells were scored between arms and made the comparison unpaired (the rule itself appeared to move 0.894 -> 0.902, which is impossible). Separate the streams (`seed` for the test side, `seed+1000` for the augmentation) so the rule column is bit-identical between arms; that is the check that proves the pairing.

Conclusion: two designed fixes have now been tried against the scored-month state plateau — season-proofing (unnecessary: a June fit transfers to December at full strength, L-038) and mask augmentation (+0.001). The remaining gap to 0.96 is not a distribution mismatch that can be closed by re-weighting the training data; it needs a different model class or features that do not exist in the release.
Evidence: `out/logs/valtest_pool8_base.log`, `out/logs/valtest_pool8_aug20b.log`, `src/state_valtest.py --augment`.
Applies when: a model underperforms in the regime with the longest blank runs. Check whether the training mask distribution actually differs before rewriting the sampler — here it did not matter at all.
