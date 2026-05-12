"""Shared data loader for tool modules."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data"


@lru_cache(maxsize=8)
def load_table(name: str) -> list[dict]:
    """Load a JSON table from data/ by filename (no extension)."""
    path = DATA_DIR / f"{name}.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))
