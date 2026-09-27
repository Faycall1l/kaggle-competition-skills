import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "kaggle-cli-ops" / "scripts"))

from common import UsageError
from exp import add_attempt, attach_result, list_runs


def test_add_list_score(tmp_path):
    ledger = tmp_path / "runs.jsonl"
    first = add_attempt(ledger, "comp-a", "neighbors", "o/k", 2, "half-window 6")
    assert first["id"] == 1
    second = add_attempt(ledger, "comp-a", "baseline", None, None, "")
    assert second["id"] == 2
    attach_result(ledger, 1, 0.8996, "complete", "ref-1")
    runs = list_runs(ledger, "comp-a")
    assert [r["id"] for r in runs] == [2, 1]
    assert runs[1]["score"] == 0.8996 and runs[1]["submission"] == "ref-1"
    assert "score" not in runs[0]


def test_add_rejects_empty(tmp_path):
    with pytest.raises(UsageError):
        add_attempt(tmp_path / "r.jsonl", " ", "m", None, None, "")


def test_score_unknown_id(tmp_path):
    ledger = tmp_path / "r.jsonl"
    add_attempt(ledger, "c", "m", None, None, "")
    with pytest.raises(UsageError):
        attach_result(ledger, 9, 0.5, "complete", None)


def test_list_filters_competition(tmp_path):
    ledger = tmp_path / "r.jsonl"
    add_attempt(ledger, "a", "m1", None, None, "")
    add_attempt(ledger, "b", "m2", None, None, "")
    assert [r["method"] for r in list_runs(ledger, "b")] == ["m2"]
    assert len(list_runs(ledger, None)) == 2
    assert list_runs(tmp_path / "missing.jsonl", None) == []


def test_latest_result_wins(tmp_path):
    ledger = tmp_path / "r.jsonl"
    add_attempt(ledger, "c", "m", None, None, "")
    attach_result(ledger, 1, 0.5, "complete", None)
    attach_result(ledger, 1, 0.6, "complete", "ref-2")
    assert list_runs(ledger, "c")[0]["score"] == 0.6
