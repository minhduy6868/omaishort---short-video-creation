from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API = Path(__file__).resolve().parent


def ensure_sys_path() -> None:
    for folder in (ROOT / "packages" / "schema", API):
        text = str(folder)
        if text not in sys.path:
            sys.path.insert(0, text)
