"""
Local watchlist storage for the BDO Market Intelligence dashboard.

The watchlist is intentionally stored outside source control. It represents a
player's personal item choices, not shared application data.
"""

import json
from pathlib import Path

# Keep the watchlist next to runtime data so it is easy to find while learning.
WATCHLIST_PATH = Path(__file__).resolve().parent.parent / "data" / "watchlist.json"


def make_item_key(item_id: int, enhancement_level: int = 0) -> str:
    """
    Build a stable watchlist key from an item ID and enhancement level.

    Args:
        item_id: The numeric BDO item ID.
        enhancement_level: The enhancement level, called ``sid`` by Arsha.

    Returns:
        A string such as ``9213:0`` that can be safely stored in JSON.
    """
    return f"{int(item_id)}:{int(enhancement_level)}"


def parse_item_key(item_key: str) -> tuple[int, int]:
    """
    Split a stored watchlist key back into item ID and enhancement level.

    Args:
        item_key: A key produced by ``make_item_key``.

    Returns:
        A tuple of ``(item_id, enhancement_level)``.
    """
    item_id, enhancement_level = item_key.split(":", maxsplit=1)
    return int(item_id), int(enhancement_level)


def load_watchlist(path: Path = WATCHLIST_PATH) -> list[str]:
    """
    Read the saved watchlist from disk.

    Args:
        path: Optional override used by tests.

    Returns:
        A de-duplicated list of item keys. Missing or invalid files return an
        empty list so the dashboard can still start cleanly.
    """
    if not path.exists():
        return []

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    if not isinstance(payload, dict):
        return []

    keys = payload.get("items", [])
    if not isinstance(keys, list):
        return []

    return _dedupe_keys([str(key) for key in keys])


def save_watchlist(item_keys: list[str], path: Path = WATCHLIST_PATH) -> None:
    """
    Persist item keys to disk.

    Args:
        item_keys: Watchlist keys to store.
        path: Optional override used by tests.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "items": _dedupe_keys(item_keys),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def add_to_watchlist(existing_keys: list[str], item_key: str) -> list[str]:
    """
    Return a new watchlist containing ``item_key``.

    Args:
        existing_keys: Current watchlist keys.
        item_key: The item key to add.

    Returns:
        A de-duplicated list preserving the user's original order.
    """
    return _dedupe_keys([*existing_keys, item_key])


def remove_from_watchlist(existing_keys: list[str], item_keys_to_remove: list[str]) -> list[str]:
    """
    Return a new watchlist without the selected item keys.

    Args:
        existing_keys: Current watchlist keys.
        item_keys_to_remove: Keys the user chose to remove.

    Returns:
        A de-duplicated list with selected keys removed.
    """
    blocked = set(item_keys_to_remove)
    return [key for key in _dedupe_keys(existing_keys) if key not in blocked]


def _dedupe_keys(item_keys: list[str]) -> list[str]:
    """
    Remove duplicate keys while preserving order.

    A normal ``set`` would remove duplicates, but it would also scramble the
    display order. Keeping the user's order makes the watchlist feel stable.
    """
    seen = set()
    deduped = []
    for key in item_keys:
        if key in seen:
            continue
        seen.add(key)
        deduped.append(key)
    return deduped
