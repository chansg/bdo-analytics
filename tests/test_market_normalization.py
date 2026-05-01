import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = PROJECT_ROOT / "bdo-intelligence"
sys.path.insert(0, str(APP_ROOT))

from api.market import (  # noqa: E402
    _apply_item_category_index,
    _history_from_v1_result,
    _infer_category_from_name,
    _normalize_item,
    _normalize_items,
    summarize_data_health,
)


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


def test_apply_item_category_index_enriches_unknown_hot_item_category():
    """Hot items without category data should use the category lookup."""
    items = [
        {
            "id": 4468,
            "name": "Red Crystal",
            "mainCategory": 0,
            "mainCategoryName": "Unknown",
            "subCategory": 0,
        }
    ]
    category_index = {
        "4468": {
            "mainCategory": 50,
            "mainCategoryName": "Magic Crystal",
            "subCategory": 1,
        }
    }

    enriched = _apply_item_category_index(items, category_index)

    assert enriched[0]["mainCategory"] == 50
    assert enriched[0]["mainCategoryName"] == "Magic Crystal"
    assert enriched[0]["subCategory"] == 1


def test_apply_item_category_index_keeps_known_categories():
    """Existing category names should not be overwritten by the lookup."""
    items = [
        {
            "id": 9213,
            "name": "Beer",
            "mainCategory": 35,
            "mainCategoryName": "Cooking",
            "subCategory": 1,
        }
    ]
    category_index = {
        "9213": {
            "mainCategory": 35,
            "mainCategoryName": "Consumable",
            "subCategory": 1,
        }
    }

    enriched = _apply_item_category_index(items, category_index)

    assert enriched[0]["mainCategoryName"] == "Cooking"


def test_infer_category_from_name_handles_hot_item_edge_cases():
    """Clear item-name patterns should avoid an Unknown category label."""
    assert _infer_category_from_name("Special Hot Pepper Seed")["mainCategoryName"] == "Seed / Hypha"
    assert _infer_category_from_name("Balenos Fishing Rod")["mainCategoryName"] == "Fishing Gear"
    assert _infer_category_from_name("[Donkey] Shabby Leather Barding")["mainCategoryName"] == "Mount Gear"
    assert _infer_category_from_name("Forest Path Wagon Flag")["mainCategoryName"] == "Wagon Part"


def test_history_from_v1_result_builds_date_price_mapping():
    """The v1 history alias should become the chart-friendly history shape."""
    payload = {"resultCode": 0, "resultMsg": "100-110-120"}

    history = _history_from_v1_result(payload, item_id=9213, source="live")

    assert history["_mock"] is False
    assert history["itemId"] == 9213
    assert list(history["history"].values()) == [100, 110, 120]


def test_data_health_is_live_when_all_loaded_endpoints_are_live():
    """The top banner should show LIVE only when every loaded endpoint is live."""
    health = summarize_data_health(
        [
            {"source": "live", "error": None},
            {"source": "live", "error": None},
        ]
    )

    assert health["state"] == "LIVE"
    assert health["icon"] == "🟢"


def test_data_health_is_partial_live_when_sources_are_mixed():
    """Mixed live/mock sources should be labelled as partial live."""
    health = summarize_data_health(
        [
            {"source": "live", "error": None},
            {"source": "mock", "error": "Arsha endpoint unavailable"},
        ]
    )

    assert health["state"] == "PARTIAL LIVE"
    assert health["icon"] == "🟠"


def test_data_health_is_mock_when_all_loaded_endpoints_are_mock():
    """The banner should say MOCK when every loaded endpoint is fallback data."""
    health = summarize_data_health(
        [
            {"source": "mock", "error": "Arsha endpoint unavailable"},
            {"source": "mock", "error": "Arsha endpoint unavailable"},
        ]
    )

    assert health["state"] == "MOCK"
    assert health["icon"] == "🟡"
