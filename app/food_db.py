from __future__ import annotations

import re
from typing import Any

from app import config
from app.storage import load_json


def load_foods() -> dict[str, dict[str, Any]]:
    raw = load_json(config.FOODS_PATH, {})
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for k, v in raw.items():
        if isinstance(k, str) and isinstance(v, dict) and "kcal" in v:
            out[k.strip().lower()] = v
    return out


def resolve_food(name: str) -> tuple[str | None, int | None]:
    """
    Returns (canonical_key_or_none, kcal_or_none).
    Matches exact lower key, then substring containment (longest key wins).
    """
    foods = load_foods()
    if not foods:
        return None, None
    n = name.strip().lower()
    if not n:
        return None, None
    if n in foods:
        kcal = int(foods[n]["kcal"])
        return n, kcal
    best_key: str | None = None
    best_len = -1
    for key in foods:
        if key in n or n in key:
            if len(key) > best_len:
                best_len = len(key)
                best_key = key
    if best_key is None:
        return None, None
    return best_key, int(foods[best_key]["kcal"])


def parse_manual_kcal(text: str) -> tuple[str, int] | None:
    """
    'pizza|450' or 'pizza : 450' → ('pizza', 450)
    """
    m = re.match(r"^(.+?)\s*[|:]\s*(\d+)\s*$", text.strip())
    if not m:
        return None
    return m.group(1).strip(), int(m.group(2))
