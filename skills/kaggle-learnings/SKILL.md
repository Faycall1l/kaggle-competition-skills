---
name: kaggle-learnings
description: "File-based learning memory for Kaggle work: capture durable findings, recall relevant ones before acting, archive stale entries. Use when the user says capture/recall/review learnings, or before non-trivial competition decisions."
license: MIT
compatibility: "Python 3.11+ for scripts/kln.py; markdown only otherwise"
metadata: {"author": "Faycall1l", "version": "0.1.0"}
---

# Kaggle Learnings

## When to activate

- User asks to record a finding, mistake, or validated pattern.
- Before a non-trivial competition decision (recall relevant learnings first).
- At session end, to extract durable findings.
- User asks to list, search, or archive stored learnings.

## When NOT to use

- CLI execution or submission decisions — see `kaggle-cli-ops`.
- Modeling methodology questions — see `kaggle-playbook`.
- Ephemeral session notes with no reuse value — do not store.

## Storage format

One markdown file per learning under `.learnings/`, named `L-<nnn>-<slug>.md`:

```markdown
# <title>
Date: <yyyy-mm-dd>
Competition: <slug or beers>
Finding: <one paragraph, specific and falsifiable>
Evidence: <command output, score delta, or log excerpt>
Applies when: <trigger conditions>
```

## Instructions

1. Recall: `python scripts/kln.py list [--competition slug] [--query term]`
   before plans, experiments, and submissions. Cite applied learnings.
2. Capture only surprises and validated patterns — findings that change future
   behavior. Format per Storage format above via
   `python scripts/kln.py add --title ... --finding ...`.
3. Archive, never delete: `python scripts/kln.py archive <id> --reason ...`.
4. Keep each file to one finding. Split multi-finding notes.

## Example

User: "GPU run OOMed on full data — record that."

1. `python scripts/kln.py add --title "P100 OOM above 40GB input" --competition <slug> --finding "P100 OOMs above ~40GB input; request T4 shape or shard inputs."`
2. Confirm stored ID for future recall.
