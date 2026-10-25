# A profile feature must be leave-one-day-out keyed on the full date, never on the day of month

Date: 2026-10-25
Competition: 2026-ieee-big-data-traffic-flow-bench
Finding: Two distinct traps in a link x weekday x slot profile built from the train split.
(1) Leakage: if the profile is computed over the same days that are then scored, the scored cell contributes to its own feature and the measured RMSE collapses into fantasy (speed RMSE 8.44 km/h *worse* was the tell after the fix; before the fix it looked 3x better). Use leave-one-day-out: subtract the scored day's own observed values and one from the counts.
(2) Key collision: leave-one-day-out keyed on `dayofweek` or on the day-of-month silently subtracts a *different* day's row when the scored split is another month. The validation split is 2031-03 and the private split 2031-04, both of which share day numbers 1..30 with every train month. Key the day rows on the full date string (e.g. `synthetic_mainline_2030_06_05`), so a day can only ever be matched to itself.
Evidence: state_headroom2 v2 leaked (profile built over the target day) and produced RMSE 8.44 for speed; with leave-one-day-out the same features gave 2.287 (-18.9% vs the shipped rule). The production module `state_model.py` keys on the stem, and the profile falls back to the plain grouped mean when the scored day is outside the profile window (no subtraction at all), which is the correct behaviour for a validation day.
Applies when: any target encoding on a time series with a monthly re-keyed calendar. Also: build the profile from the train split only, and let out-of-window days get the un-subtracted mean.
