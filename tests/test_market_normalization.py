import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = PROJECT_ROOT / "bdo-intelligence"
sys.path.insert(0, str(APP_ROOT))

from api.market import _history_from_v1_result, _normalize_item, _normalize_items  # noqa: E402


def test_normalize_item_maps_common_api_aliases():
    """Raw API field names should be converted into the dashboard schema."""
    raw_item = {
        "itemId": "123",
        "itemName": "Test Ingredient",
        "basePrice": "1500",
        "totalTrades": "250",
        "currentStock": "40",
    }

    item = _normalize_item(
        raw_item,
        source="live",
        category_id="35",
        sub_category_id="2",
    )

    assert item["id"] == 123
    assert item["name"] == "Test Ingredient"
    assert item["mainCategory"] == 35
    assert item["mainCategoryName"] == "Cooking"
    assert item["subCategory"] == 2
    assert item["minPrice"] == 1500
    assert item["tradeCount"] == 250
    assert item["currentStock"] == 40
    assert item["source"] == "live"


def test_normalize_items_deduplicates_same_item_and_enhancement_level():
    """If two subcategory calls return the same item, keep one row."""
    items = [
        {"id": 100, "sid": 0, "name": "Duplicate", "minPrice": 10},
        {"id": 100, "sid": 0, "name": "Duplicate", "minPrice": 10},
    ]

    normalized = _normalize_items(items, source="live")

    assert len(normalized) == 1
    assert normalized[0]["id"] == 100


def test_history_from_v1_result_builds_date_price_mapping():
    """The v1 history alias should become the chart-friendly history shape."""
    payload = {"resultCode": 0, "resultMsg": "100-110-120"}

    history = _history_from_v1_result(payload, item_id=9213, source="live")

    assert history["_mock"] is False
    assert history["itemId"] == 9213
    assert list(history["history"].values()) == [100, 110, 120]
