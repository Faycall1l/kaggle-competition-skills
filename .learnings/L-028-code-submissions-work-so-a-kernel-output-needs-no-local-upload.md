# Code submissions work: a kernel output can be submitted with no local upload

Date: 2026-10-25
Competition: 2026-ieee-big-data-traffic-flow-bench
Finding: `kaggle competitions submit -c <competition> -k <owner/kernel> -v <version> -f <file-in-output> -m <msg>` accepts the output file of a finished kernel run and creates a submission directly, consuming one daily slot but no bandwidth. The competition page reports `isKernelsSubmissionsOnly: false`, which only means plain file submissions are *also* allowed; it does not mean code submissions are disabled. Verified with `faycal00/traffic-v53storedstate` version 1, file `sub_v53storedstate.csv`: the CLI printed "4 submissions remaining today" and a new entry with `status=PENDING` appeared in `kaggle competitions submissions`.
Evidence: submission ref 57641061, description "code-submission path test (v53 duplicate)", created 2026-10-25 19:34 UTC
Applies when: a competition submission file is large enough that the local uplink is the bottleneck (here ~37 kB/s, ~80 min per 185 MB). Build the file inside the kernel and submit the kernel version instead: the download/upload both disappear, and the only cost is the kernel run, which has to happen anyway.
