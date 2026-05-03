import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = PROJECT_ROOT / "bdo-intelligence"
sys.path.insert(0, str(APP_ROOT))

from services.watchlist import (  # noqa: E402
    add_to_watchlist,
    load_watchlist,
    make_item_key,
    parse_item_key,
    remove_from_watchlist,
    save_watchlist,
)


def test_make_and_parse_item_key_round_trips_item_identity():
    """An item ID and enhancement level should survive JSON storage."""
    key = make_item_key(9213, 0)

    assert key == "9213:0"
    assert parse_item_key(key) == (9213, 0)


def test_watchlist_add_remove_keeps_order_and_prevents_duplicates():
    """Adding the same item twice should not create duplicate rows."""
    keys = add_to_watchlist([], "9213:0")
    keys = add_to_watchlist(keys, "9801:0")
    keys = add_to_watchlist(keys, "9213:0")

    assert keys == ["9213:0", "9801:0"]
    assert remove_from_watchlist(keys, ["9213:0"]) == ["9801:0"]


def test_watchlist_save_and_load_uses_json_file(tmp_path):
    """The local watchlist file should persist only the selected item keys."""
    path = tmp_path / "watchlist.json"

    save_watchlist(["9213:0", "9801:0", "9213:0"], path=path)

    assert load_watchlist(path=path) == ["9213:0", "9801:0"]
