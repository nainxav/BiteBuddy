from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, TypeVar

T = TypeVar("T")


def ensure_data_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def atomic_write_json(path: Path, data: Any) -> None:
    ensure_data_dir(path.parent)
    serialized = json.dumps(data, indent=2, ensure_ascii=False)
    fd, tmp = tempfile.mkstemp(
        dir=str(path.parent), prefix=path.name + ".", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(serialized)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
