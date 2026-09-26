import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "kaggle-learnings" / "scripts"))

from kln import add_learning, archive_learning, list_learnings, next_id, slugify


def test_slugify():
    assert slugify("P100 OOM above 40GB!") == "p100-oom-above-40gb"
    assert slugify("  ") == "untitled"


def test_add_and_list(tmp_path):
    root = tmp_path / ".learnings"
    result = add_learning(root, "T1", "F1", "titanic", "E1")
    assert result["ok"] is True and result["id"] == 1
    assert Path(result["path"]).is_file()
    listed = list_learnings(root, None, None)
    assert len(listed) == 1 and listed[0]["title"] == "T1"
    assert next_id(root) == 2


def test_add_rejects_empty():
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        with pytest.raises(ValueError):
            add_learning(Path(d), "  ", "F", "c", "")
        with pytest.raises(ValueError):
            add_learning(Path(d), "T", "  ", "c", "")


def test_list_filters(tmp_path):
    root = tmp_path / ".learnings"
    add_learning(root, "GPU note", "P100 memory", "comp-a", "")
    add_learning(root, "CV note", "folds", "comp-b", "")
    assert len(list_learnings(root, "comp-a", None)) == 1
    assert len(list_learnings(root, None, "folds")) == 1
    assert list_learnings(root, None, "missing") == []
    assert list_learnings(tmp_path / "empty", None, None) == []


def test_archive_moves_not_deletes(tmp_path):
    root = tmp_path / ".learnings"
    add_learning(root, "Old", "F", "c", "")
    result = archive_learning(root, 1, "superseded")
    assert result["ok"] is True
    assert Path(result["archived"]).is_file()
    assert "Archived:" in Path(result["archived"]).read_text()
    assert list_learnings(root, None, None) == []


def test_archive_unknown_id(tmp_path):
    root = tmp_path / ".learnings"
    root.mkdir()
    with pytest.raises(ValueError):
        archive_learning(root, 9, "reason")


def test_archive_empty_reason(tmp_path):
    root = tmp_path / ".learnings"
    add_learning(root, "T", "F", "c", "")
    with pytest.raises(ValueError):
        archive_learning(root, 1, "  ")
