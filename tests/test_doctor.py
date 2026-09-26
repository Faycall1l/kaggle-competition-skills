import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "kaggle-cli-ops" / "scripts"))

import doctor
from doctor import check_cli_version, check_quota, detect_credentials


def _home_with(tmp_path, files):
    home = tmp_path / "home"
    kdir = home / ".kaggle"
    kdir.mkdir(parents=True)
    for name, content in files.items():
        (kdir / name).write_text(content)
    return home


def test_env_token_detected(tmp_path):
    sources, _ = detect_credentials({"KAGGLE_API_TOKEN": "KGAT_x"}, tmp_path)
    assert sources == [{"source": "env:KAGGLE_API_TOKEN", "present": True}]


def test_legacy_env_pair_detected(tmp_path):
    sources, _ = detect_credentials({"KAGGLE_USERNAME": "u", "KAGGLE_KEY": "k"}, tmp_path)
    assert any(s["source"] == "env:KAGGLE_USERNAME/KAGGLE_KEY" for s in sources)


def test_legacy_env_half_pair_ignored(tmp_path):
    sources, _ = detect_credentials({"KAGGLE_USERNAME": "u"}, tmp_path)
    assert sources == []


def test_access_token_file_detected(tmp_path):
    home = _home_with(tmp_path, {"access_token": "KGAT_x"})
    sources, _ = detect_credentials({}, home)
    assert any(s["source"] == "file:access_token" for s in sources)


def test_kaggle_json_with_credentials(tmp_path):
    home = _home_with(tmp_path, {"kaggle.json": json.dumps({"username": "u", "key": "k"})})
    sources, _ = detect_credentials({}, home)
    assert {"source": "file:kaggle.json", "present": True, "has_credentials": True} in sources


def test_kaggle_json_config_only_flagged(tmp_path):
    home = _home_with(tmp_path, {"kaggle.json": json.dumps({"competition": "titanic"})})
    sources, _ = detect_credentials({}, home)
    match = [s for s in sources if s["source"] == "file:kaggle.json"]
    assert len(match) == 1 and match[0]["has_credentials"] is False


def test_kaggle_json_malformed_flagged(tmp_path):
    home = _home_with(tmp_path, {"kaggle.json": "not json{"})
    sources, _ = detect_credentials({}, home)
    match = [s for s in sources if s["source"] == "file:kaggle.json"]
    assert len(match) == 1 and match[0]["has_credentials"] is False


def test_empty_environment(tmp_path):
    sources, mode = detect_credentials({}, tmp_path)
    assert sources == [] and mode is None


def test_cli_version_missing_binary(monkeypatch):
    monkeypatch.setattr(doctor, "run_cli", lambda args, timeout=60: (127, "", "No such file"))
    result = check_cli_version()
    assert result["status"] == "error"


def test_cli_version_ok(monkeypatch):
    monkeypatch.setattr(doctor, "run_cli", lambda args, timeout=60: (0, "Kaggle CLI 2.2.4\n", ""))
    result = check_cli_version()
    assert result["status"] == "ok" and "2.2.4" in result["version"]


def test_quota_json_parsed(monkeypatch):
    monkeypatch.setattr(doctor, "run_cli", lambda args, timeout=60: (0, '{"gpu": 10}', ""))
    result = check_quota()
    assert result == {"name": "quota", "status": "ok", "quota": {"gpu": 10}}


def test_quota_non_json(monkeypatch):
    monkeypatch.setattr(doctor, "run_cli", lambda args, timeout=60: (0, "table text", ""))
    assert check_quota()["status"] == "error"


def test_quota_cli_failure(monkeypatch):
    monkeypatch.setattr(doctor, "run_cli", lambda args, timeout=60: (1, "", "403 Forbidden"))
    result = check_quota()
    assert result["status"] == "error" and "403" in result["detail"]
