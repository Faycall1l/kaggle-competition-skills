import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "examples" / "traffic-flow-v2"))

from pack import build_bootstrap

REPO = Path(__file__).resolve().parent.parent


def test_bootstrap_verifies_entry_points(tmp_path):
    good = tmp_path / "good.py"
    good.write_text("def main():\n    pass\n")
    cell = build_bootstrap({"good.py": good}, {"good.py": ["main"]})
    assert any("_BUNDLE" in line for line in cell)


def test_bootstrap_rejects_missing_names(tmp_path):
    bad = tmp_path / "bad.py"
    bad.write_text("X = 1\n")
    import pytest

    with pytest.raises(ValueError):
        build_bootstrap({"bad.py": bad}, {"bad.py": ["main"]})


def test_bootstrap_rejects_syntax_error(tmp_path):
    broken = tmp_path / "broken.py"
    broken.write_text("def broken(:\n")
    import pytest

    with pytest.raises(SyntaxError):
        build_bootstrap({"broken.py": broken}, {})
