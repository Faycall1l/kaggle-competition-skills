"""Pack helper files into a notebook bootstrap cell with verification.

Dataset mounts can lag published versions, so code under active iteration is
embedded in the notebook instead. The payload is base64-encoded: notebook
cell preprocessing (nbconvert escape handling) must never be able to alter
the embedded bytes. Verification parses each payload file and asserts the
expected entry points exist before the notebook is generated.
"""

from __future__ import annotations

import ast
import base64
from pathlib import Path


def build_bootstrap(files: dict[str, Path], required_names: dict[str, list[str]]) -> list[str]:
    """Return notebook cell source embedding files. Raises on any defect."""
    payload: dict[str, str] = {}
    for name, path in files.items():
        text = path.read_text()
        tree = ast.parse(text)
        defined = {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
        missing = [n for n in required_names.get(name, []) if n not in defined]
        if missing:
            raise ValueError(f"{path} is missing required definitions: {missing}")
        payload[name] = base64.b64encode(text.encode("utf-8")).decode("ascii")
    return [
        "from pathlib import Path\n",
        "import base64 as _b64\n",
        "_EMBED = " + repr(payload) + "\n",
        "_BUNDLE = Path('/kaggle/working/_bundle')\n",
        "_BUNDLE.mkdir(exist_ok=True)\n",
        "for _name, _b64text in _EMBED.items():\n",
        "    (_BUNDLE / _name).write_text(_b64.b64decode(_b64text).decode('utf-8'))\n",
        "import sys as _s\n",
        "_s.path.insert(0, str(_BUNDLE))\n",
        "_v1 = next(Path('/kaggle/input').rglob('build_task1_baseline_submission.py'))\n",
        "_s.path.insert(0, str(_v1.parent.parent))\n",
        "import os as _o\n",
        "_o.environ['PYTHONPATH'] = str(_BUNDLE) + ':' + str(_v1.parent.parent)\n",
        "print('embedded:', sorted(p.name for p in _BUNDLE.glob('*.py')))\n",
    ]
