import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "kaggle-cli-ops" / "scripts"))

import comp_submit
from common import BlockedError, UsageError
from comp_submit import (
    check_allowance,
    check_file,
    check_kernel_submittable,
    leaderboard,
    normalize_status,
    poll,
    ref_by_description,
    send,
    submission_state,
    submit,
)


def _ok_allowance(monkeypatch):
    monkeypatch.setattr(comp_submit, "run_cli", lambda cmd, timeout: (0, '{"numAllowedNow": 3}', ""))


def test_submit_bad_slug():
    with pytest.raises(UsageError):
        submit("owner/slug", file="f.csv", message="m", kernel=None, version=None, wait=False)


def test_submit_kernel_without_version():
    with pytest.raises(UsageError):
        submit("titanic", file="o.csv", message="m", kernel="owner/slug", version=None, wait=False)


def test_submit_happy(monkeypatch, tmp_path):
    f = tmp_path / "sub.csv"
    f.write_text("id,x\n1,2\n")
    monkeypatch.chdir(tmp_path)
    _ok_allowance(monkeypatch)
    monkeypatch.setattr(comp_submit, "send", lambda *a: "ref-1")
    assert submit("titanic", file=str(f), message="m", kernel=None, version=None, wait=False)["ref"] == "ref-1"


def test_check_allowance_exhausted(monkeypatch):
    monkeypatch.setattr(comp_submit, "run_cli", lambda cmd, timeout: (0, '{"numAllowedNow": 0}', ""))
    with pytest.raises(BlockedError):
        check_allowance("titanic")


def test_check_allowance_uses_json_flag(monkeypatch):
    seen = {}

    def fake_run(cmd, timeout):
        seen["cmd"] = cmd
        return (0, '{"numAllowedNow": 3}', "")

    monkeypatch.setattr(comp_submit, "run_cli", fake_run)
    check_allowance("titanic")
    assert "--json" in seen["cmd"]


def test_normalize_status():
    assert normalize_status("SubmissionStatus.COMPLETE") == "complete"
    assert normalize_status("SubmissionStatus.ERROR") == "error"
    assert normalize_status("pending") == "pending"


def test_submission_state_enum_prefix(monkeypatch):
    rows = json.dumps([{"ref": 45668828, "fileName": "submission.csv", "status": "SubmissionStatus.COMPLETE"}])
    monkeypatch.setattr(comp_submit, "run_cli", lambda cmd, timeout: (0, rows, ""))
    assert submission_state("c", "45668828") == "complete"


def test_submission_state_empty_history_400(monkeypatch):
    monkeypatch.setattr(
        comp_submit,
        "run_cli",
        lambda cmd, timeout: (1, "", "400 Client Error for url: CompetitionApiService/ListSubmissions"),
    )
    assert submission_state("c", "r") == "unknown"


def test_check_allowance_cli_failure(monkeypatch):
    monkeypatch.setattr(comp_submit, "run_cli", lambda cmd, timeout: (1, "", "denied"))
    with pytest.raises(BlockedError):
        check_allowance("titanic")


def test_check_file_missing(tmp_path):
    with pytest.raises(UsageError):
        check_file(str(tmp_path / "nope.csv"), "titanic")


def test_check_file_header_mismatch(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "titanic").mkdir()
    (tmp_path / "titanic" / "data").mkdir()
    (tmp_path / "titanic" / "data" / "sample_submission.csv").write_text("id,x\n")
    bad = tmp_path / "bad.csv"
    bad.write_text("id,y\n")
    with pytest.raises(BlockedError):
        check_file(str(bad), "titanic")


def test_check_file_header_ok(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "titanic").mkdir()
    (tmp_path / "titanic" / "data").mkdir()
    (tmp_path / "titanic" / "data" / "sample_submission.csv").write_text("id,x\n")
    good = tmp_path / "good.csv"
    good.write_text("id,x\n1,2\n")
    check_file(str(good), "titanic")


def test_check_kernel_versioned_rejected():
    with pytest.raises(UsageError):
        check_kernel_submittable("owner/slug/3")


def test_check_kernel_internet_rejected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "my-kernel").mkdir()
    (tmp_path / "my-kernel" / "kernel-metadata.json").write_text(
        json.dumps({"id": "u/my-kernel", "enable_internet": True})
    )
    with pytest.raises(BlockedError):
        check_kernel_submittable("u/my-kernel")


def test_send_403_browser_fallback(monkeypatch):
    monkeypatch.setattr(comp_submit, "run_cli", lambda cmd, timeout: (1, "", "403 kernelSessions.get denied"))
    with pytest.raises(BlockedError) as exc:
        send("c", "f.csv", "m", "o/s", "2")
    assert "browser" in exc.value.next_action


def test_send_failure(monkeypatch):
    monkeypatch.setattr(comp_submit, "run_cli", lambda cmd, timeout: (1, "", "bad file"))
    with pytest.raises(BlockedError):
        send("c", "f.csv", "m", None, None)


def test_send_ref_parsed(monkeypatch):
    monkeypatch.setattr(comp_submit, "run_cli", lambda cmd, timeout: (0, "Submission ref: abc-123", ""))
    assert send("c", "f.csv", "m", None, None) == "abc-123"


def test_send_falls_back_to_description(monkeypatch):
    rows = json.dumps([{"ref": 11, "description": "old"}, {"ref": 22, "description": "m"}])
    calls = iter([(0, "uploaded ok", ""), (0, rows, "")])
    monkeypatch.setattr(comp_submit, "run_cli", lambda cmd, timeout: next(calls))
    assert send("c", "f.csv", "m", None, None) == "22"


def test_send_no_ref_no_row(monkeypatch):
    calls = iter([(0, "uploaded ok", ""), (0, "[]", "")])
    monkeypatch.setattr(comp_submit, "run_cli", lambda cmd, timeout: next(calls))
    with pytest.raises(BlockedError):
        send("c", "f.csv", "m", None, None)


def test_ref_by_description_newest(monkeypatch):
    rows = json.dumps(
        [
            {"ref": 1, "description": "m", "date": "2026-01-01"},
            {"ref": 2, "description": "m", "date": "2026-01-02"},
            {"ref": 3, "description": "other", "date": "2026-01-03"},
        ]
    )
    monkeypatch.setattr(comp_submit, "run_cli", lambda cmd, timeout: (0, rows, ""))
    assert ref_by_description("c", "m") == "2"


def test_poll_complete(monkeypatch):
    monkeypatch.setattr(comp_submit, "submission_state", lambda c, r: "complete")
    monkeypatch.setattr(comp_submit.time, "sleep", lambda s: None)
    assert poll("c", "ref") == {"state": "complete"}


def test_submission_state_lookup(monkeypatch):
    rows = json.dumps([{"ref": "r1", "status": "complete"}, {"ref": "r2", "status": "pending"}])
    monkeypatch.setattr(comp_submit, "run_cli", lambda cmd, timeout: (0, rows, ""))
    assert submission_state("c", "r2") == "pending"
    assert submission_state("c", "missing") == "unknown"


def test_submission_state_non_json(monkeypatch):
    monkeypatch.setattr(comp_submit, "run_cli", lambda cmd, timeout: (0, "table", ""))
    assert submission_state("c", "r") == "unknown"


def test_leaderboard_top(monkeypatch):
    rows = json.dumps([{"team": i} for i in range(20)])
    monkeypatch.setattr(comp_submit, "run_cli", lambda cmd, timeout: (0, rows, ""))
    assert len(leaderboard("c", top=10)) == 10


def test_leaderboard_failure(monkeypatch):
    monkeypatch.setattr(comp_submit, "run_cli", lambda cmd, timeout: (1, "", "nope"))
    with pytest.raises(BlockedError):
        leaderboard("c")
