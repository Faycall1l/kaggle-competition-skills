import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "kaggle-cli-ops" / "scripts"))

from common import BlockedError, UsageError, backoff_delays, emit, parse_dataset_ref, parse_kernel_ref, run_cli


def test_emit_writes_json(capsys):
    emit({"ok": True})
    assert capsys.readouterr().out.strip() == '{"ok": true}'


def test_parse_kernel_ref_two_parts():
    assert parse_kernel_ref("owner/slug") == ("owner", "slug", None)


def test_parse_kernel_ref_version():
    assert parse_kernel_ref("owner/slug/3") == ("owner", "slug", "3")
    assert parse_kernel_ref("owner/slug/v3") == ("owner", "slug", "v3")


def test_parse_kernel_ref_trailing_slash():
    assert parse_kernel_ref("owner/slug/") == ("owner", "slug", None)


def test_parse_kernel_ref_invalid():
    for bad in ["", "slug", "a/b/c/d", "/slug", "owner/"]:
        with pytest.raises(UsageError):
            parse_kernel_ref(bad)


def test_parse_dataset_ref_forms():
    assert parse_dataset_ref("slug") == (None, "slug", None)
    assert parse_dataset_ref("owner/slug") == ("owner", "slug", None)
    assert parse_dataset_ref("owner/slug/2") == ("owner", "slug", "2")


def test_parse_dataset_ref_invalid():
    for bad in ["", "a/b/c/d"]:
        with pytest.raises(UsageError):
            parse_dataset_ref(bad)


def test_backoff_delays_shape():
    assert backoff_delays(1) == []
    assert backoff_delays(4, base=5.0) == [5.0, 10.0, 20.0]
    assert backoff_delays(5, base=200.0, cap=300.0)[-1] == 300.0


def test_backoff_delays_invalid():
    with pytest.raises(UsageError):
        backoff_delays(0)


def test_blocked_error_carries_next_action():
    err = BlockedError("no quota", "run doctor.py")
    assert err.next_action == "run doctor.py"


def test_run_cli_missing_binary():
    code, out, err = run_cli(["--version"], binary="definitely-not-a-binary-xyz")
    assert code == 127 and out == "" and err
