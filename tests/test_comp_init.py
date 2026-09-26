import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "kaggle-cli-ops" / "scripts"))

import comp_init
from common import BlockedError, UsageError
from comp_init import download, extract, initialize


def _fake_zip(path: Path, members=("train.csv",)):
    with zipfile.ZipFile(path, "w") as zf:
        for m in members:
            zf.writestr(m, "a,b\n1,2\n")


def test_initialize_bad_slug(tmp_path):
    with pytest.raises(UsageError):
        initialize("owner/slug", parent=tmp_path, file=None, force=False, unzip=True)
    with pytest.raises(UsageError):
        initialize("", parent=tmp_path, file=None, force=False, unzip=True)


def test_initialize_happy_path(monkeypatch, tmp_path):
    def fake_download(slug, dest, file, force):
        assert slug == "titanic" and force is False
        archive = dest / "titanic.zip"
        _fake_zip(archive)
        return archive

    monkeypatch.setattr(comp_init, "download", fake_download)
    result = initialize("titanic", parent=tmp_path, file=None, force=False, unzip=True)
    assert result["ok"] is True
    assert result["extracted"] == ["train.csv"]
    assert (tmp_path / "titanic" / "data" / "train.csv").is_file()
    assert (tmp_path / "titanic" / "submissions").is_dir()
    assert (tmp_path / "titanic" / "README.md").is_file()


def test_initialize_no_unzip(monkeypatch, tmp_path):
    monkeypatch.setattr(comp_init, "download", lambda slug, dest, file, force: dest / "titanic.zip")
    result = initialize("titanic", parent=tmp_path, file=None, force=False, unzip=False)
    assert result["extracted"] == []


def test_download_cli_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(comp_init, "run_cli", lambda cmd, timeout: (1, "", "403 Forbidden"))
    with pytest.raises(BlockedError) as exc:
        download("titanic", tmp_path, file=None, force=False)
    assert "kaggle.com/c/titanic" in exc.value.next_action


def test_download_skipping_local_copy(monkeypatch, tmp_path):
    monkeypatch.setattr(
        comp_init,
        "run_cli",
        lambda cmd, timeout: (0, "titanic.zip: Skipping, found more recently modified local copy", ""),
    )
    with pytest.raises(BlockedError):
        download("titanic", tmp_path, file=None, force=False)


def test_download_force_warns(monkeypatch, tmp_path, capsys):
    seen = {}

    def fake_run(cmd, timeout):
        seen["cmd"] = cmd
        return (0, "Downloading", "")

    monkeypatch.setattr(comp_init, "run_cli", fake_run)
    download("titanic", tmp_path, file=None, force=True)
    assert "--force" in seen["cmd"]
    assert "WARNING" in capsys.readouterr().err


def test_extract_non_zip(tmp_path):
    plain = tmp_path / "data.txt"
    plain.write_text("x")
    assert extract(plain, True) == []
    assert extract(None, True) == []
