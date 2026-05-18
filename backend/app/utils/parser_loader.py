"""Utilities for loading the existing parser modules from their folders."""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def ensure_parser_paths() -> tuple[str, str]:
    backend_root = Path(__file__).resolve().parents[2]
    top_down = str(backend_root / "TopDown")
    bottom_up = str(backend_root / "BottomUp")

    for path in (top_down, bottom_up):
        if path not in sys.path:
            sys.path.insert(0, path)

    return top_down, bottom_up
