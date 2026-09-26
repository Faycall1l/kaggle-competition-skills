import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "kaggle-cli-ops" / "scripts"))

import kernel_push
from common import BlockedError, UsageError
from kernel_push import (
    download_output,
    fetch_logs,
    parse_status,
    poll_status,
    push,
    push_version,
    read_kernel_slug,
    resolve_kernel_ref,
)


def _kernel_dir(tmp_path, ref="owner/slug"):
    d = tmp_path / "kernel"
    d.mkdir()
    (d / "kernel-metadata.json").write_text(json.dumps({"id": ref, "title": "t"}))
    return d


def test_read_kernel_slug_ok(tmp_path):
    assert read_kernel_slug(_kernel_dir(tmp_path)) == "owner/slug"


def test_read_kernel_slug_missing(tmp_path):
    with pytest.raises(UsageError):
        read_kernel_slug(tmp_path)


def test_read_kernel_slug_versioned_rejected(tmp_path):
    with pytest.raises(UsageError):
        read_kernel_slug(_kernel_dir(tmp_path, ref="owner/slug/3"))


def test_read_kernel_slug_malformed(tmp_path):
    d = tmp_path / "k"
    d.mkdir()
    (d / "kernel-metadata.json").write_text("{}")
    with pytest.raises(UsageError):
        read_kernel_slug(d)


def test_push_version_parses(monkeypatch, tmp_path):
    monkeypatch.setattr(kernel_push, "run_cli", lambda cmd, timeout: (0, "Kernel version 7 successfully pushed", ""))
    assert push_version(tmp_path, timeout=None, accelerator=None, no_run=False) == 7


def test_push_version_flags(monkeypatch, tmp_path):
    seen = {}

    def fake_run(cmd, timeout):
        seen["cmd"] = cmd
        return (0, "Kernel version 1 ok", "")

    monkeypatch.setattr(kernel_push, "run_cli", fake_run)
    push_version(tmp_path, timeout=60, accelerator="NvidiaTeslaT4", no_run=True)
    assert "--timeout" in seen["cmd"] and "--accelerator" in seen["cmd"] and "--no-run" in seen["cmd"]


def test_push_version_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(kernel_push, "run_cli", lambda cmd, timeout: (1, "", "403 Forbidden"))
    with pytest.raises(BlockedError):
        push_version(tmp_path, timeout=None, accelerator=None, no_run=False)


def test_push_version_missing_number(monkeypatch, tmp_path):
    monkeypatch.setattr(kernel_push, "run_cli", lambda cmd, timeout: (0, "pushed ok", ""))
    with pytest.raises(BlockedError):
        push_version(tmp_path, timeout=None, accelerator=None, no_run=False)


def test_parse_status_states():
    assert parse_status("COMPLETE") == "COMPLETE"
    assert parse_status("error") == "ERROR"
    assert parse_status("QUEUED") == "QUEUED"


def test_parse_status_unknown():
    with pytest.raises(BlockedError):
        parse_status("??? ")


def test_poll_complete(monkeypatch):
    calls = iter([(0, "RUNNING", ""), (0, "COMPLETE", "")])
    monkeypatch.setattr(kernel_push, "run_cli", lambda cmd, timeout: next(calls))
    monkeypatch.setattr(kernel_push.time, "sleep", lambda s: None)
    assert poll_status("o/s", 2) == {"state": "COMPLETE", "kernel": "o/s"}


def test_poll_error_fetches_logs(monkeypatch):
    monkeypatch.setattr(
        kernel_push, "run_cli", lambda cmd, timeout: (0, "ERROR", "") if "status" in cmd else (0, "traceback line", "")
    )
    monkeypatch.setattr(kernel_push.time, "sleep", lambda s: None)
    result = poll_status("o/s", 2)
    assert result["state"] == "ERROR" and "traceback" in result["logs_tail"]


def test_poll_slug_mismatch_resolves(monkeypatch):
    calls = iter(
        [
            (1, "", "wrong kernel slug, use kaggle.com/code/owner/REAL"),
            (0, '[{"ref": "real/slug", "title": "T"}]', ""),
            (0, "COMPLETE", ""),
        ]
    )
    monkeypatch.setattr(kernel_push, "run_cli", lambda cmd, timeout: next(calls))
    monkeypatch.setattr(kernel_push.time, "sleep", lambda s: None)
    assert poll_status("wrong/slug", 1, title="T") == {"state": "COMPLETE", "kernel": "real/slug"}


def test_resolve_no_match(monkeypatch):
    monkeypatch.setattr(kernel_push, "run_cli", lambda cmd, timeout: (0, "[]", ""))
    with pytest.raises(BlockedError):
        resolve_kernel_ref("Missing")


def test_fetch_logs_failure(monkeypatch):
    monkeypatch.setattr(kernel_push, "run_cli", lambda cmd, timeout: (1, "", "boom"))
    assert fetch_logs("o/s", 1) == "boom"


def test_download_output_lists_files(monkeypatch, tmp_path):
    (tmp_path / "a.csv").write_text("x")
    monkeypatch.setattr(kernel_push, "run_cli", lambda cmd, timeout: (0, "ok", ""))
    result = download_output("o/s", 1, tmp_path)
    assert result["files"] == ["a.csv"]


def test_download_output_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(kernel_push, "run_cli", lambda cmd, timeout: (1, "", "nope"))
    with pytest.raises(BlockedError):
        download_output("o/s", 1, tmp_path)


def test_push_no_wait(monkeypatch, tmp_path):
    d = _kernel_dir(tmp_path)
    monkeypatch.setattr(kernel_push, "run_cli", lambda cmd, timeout: (0, "Kernel version 4 ok", ""))
    assert push(str(d), timeout=None, accelerator=None, no_run=False, wait=False) == {
        "ok": True,
        "kernel": "owner/slug",
        "version": 4,
    }
