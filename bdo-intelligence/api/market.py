"""
BDO Market API wrapper with caching and mock fallback.

Connects to the BDO EU Central Market via arsha.io (community proxy).
All responses are cached as JSON files with a 15-minute TTL.
If the API is unreachable, realistic mock data is returned instead.
"""

import asyncio
import json
import logging
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache"
CACHE_TTL_SECONDS = 15 * 60  # 15 minutes
ARSHA_BASE_URL = "https://api.arsha.io"
REGION = "eu"
LANGUAGE = "en"
REQUEST_TIMEOUT_SECONDS = 20
MAX_SUBCATEGORY_SCAN = 30

# BDO category IDs
COOKING_MAIN_CATEGORY = "35"   # Cooking in arsha.io V2 category mapping
ALCHEMY_MAIN_CATEGORY = "45"   # Alchemy
MARKET_MAIN_CATEGORIES = {
    "1": "Main Weapon",
    "5": "Sub-Weapon",
    "10": "Awakening Weapon",
    "15": "Armor",
    "20": "Accessory",
    "25": "Material",
    "30": "Enhancement",
    "35": "Consumable",
    "40": "Life Tool",
    "45": "Alchemy Stone",
    "50": "Magic Crystal",
    "55": "Pearl Item",
    "60": "Dye",
    "65": "Pet",
    "70": "Ship",
    "75": "Wagon",
    "80": "Furniture",
    "85": "Lightstone",
}
CRAFTING_CATEGORY_SUBCATEGORIES = {
    COOKING_MAIN_CATEGORY: ("1", "2", "3"),
    ALCHEMY_MAIN_CATEGORY: ("1", "2", "3"),
}
CATEGORY_NAMES = {
    **MARKET_MAIN_CATEGORIES,
    # These labels are used for the focused browser view. They are intentionally
    # more player-friendly than the broad Central Market category names.
    COOKING_MAIN_CATEGORY: "Cooking",
    ALCHEMY_MAIN_CATEGORY: "Alchemy",
}

LOGGER = logging.getLogger(__name__)


class ArshaApiError(RuntimeError):
    """Raised when the public Arsha API returns an error response."""

# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


def _cache_path(key: str) -> Path:
    """Return the file path for a given cache key."""
    return CACHE_DIR / f"{key}.json"


def _read_cache_entry(key: str) -> Optional[dict]:
    """
    Read a cached wrapper if it exists and is fresher than CACHE_TTL_SECONDS.

    Args:
        key: A unique string identifying this cached response.

    Returns:
        The cached wrapper dict, or None if stale or missing.
    """
    path = _cache_path(key)
    if not path.exists():
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            wrapper = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    cached_at = wrapper.get("cached_at", 0)
    if time.time() - cached_at > CACHE_TTL_SECONDS:
        return None  # stale

    return wrapper


def _read_cache(key: str) -> Optional[Any]:
    """
    Read cached data if it exists and is fresher than CACHE_TTL_SECONDS.

    Args:
        key: A unique string identifying this cached response.

    Returns:
        The cached data as a dict/list, or None if stale or missing.
    """
    wrapper = _read_cache_entry(key)
    if wrapper is None:
        return None
    return wrapper.get("data")


def _write_cache(
    key: str,
    data: Any,
    source: str = "live",
    error: Optional[str] = None,
) -> None:
    """
    Write data to a JSON cache file with the current timestamp.

    Args:
        key: A unique string identifying this cached response.
        data: The API response data to cache.
        source: Where the data came from (live, mock, cached-live, etc.).
        error: Optional error message that caused a fallback.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    wrapper = {
        "cached_at": time.time(),
        "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": source,
        "error": error,
        "data": data,
    }
    with open(_cache_path(key), "w", encoding="utf-8") as f:
        json.dump(wrapper, f, indent=2, default=str)


def clear_cache() -> None:
    """Delete all cached JSON files so the next call fetches fresh data."""
    if CACHE_DIR.exists():
        for file in CACHE_DIR.glob("*.json"):
            file.unlink()


def is_using_live_data(key: str) -> bool:
    """
    Check whether the most recent data for *key* came from a live API call.

    Returns True if a valid (non-stale) cache file exists whose data does NOT
    contain the ``_mock`` sentinel flag.
    """
    status = get_data_status(key)
    if status["source"] != "live":
        return False
    return True


def get_data_status(key: str) -> dict[str, Any]:
    """
    Return cache/source metadata for a cached dataset.

    Args:
        key: A cache key such as ``hot_items`` or ``cooking_items``.

    Returns:
        A small dict with source, fetched_at, cached_at, and error fields.
    """
    wrapper = _read_cache_entry(key)
    if wrapper is None:
        return {
            "key": key,
            "source": "unknown",
            "fetched_at": None,
            "cached_at": None,
            "error": None,
        }

    source = wrapper.get("source")
    data = wrapper.get("data")
    if source is None:
        source = "mock" if _contains_mock_data(data) else "live"

    return {
        "key": key,
        "source": source,
        "fetched_at": wrapper.get("fetched_at"),
        "cached_at": wrapper.get("cached_at"),
        "error": wrapper.get("error"),
    }


def summarize_data_health(statuses: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Summarize several endpoint statuses into one dashboard health state.

    A single banner that says only LIVE or MOCK can be misleading. For example,
    Cooking/Alchemy category data may be live while Hot Items is using mock
    fallback because the upstream endpoint is blocked. This helper makes that
    mixed state explicit.
    """
    known_statuses = [status for status in statuses if status.get("source") != "unknown"]
    if not known_statuses:
        return {
            "state": "UNKNOWN",
            "message": "Data source will appear after the first load.",
            "icon": "ℹ️",
        }

    sources = {status.get("source") for status in known_statuses}
    if sources == {"live"}:
        return {
            "state": "LIVE",
            "message": "All loaded endpoints are live via arsha.io.",
            "icon": "🟢",
        }
    if "live" in sources and "mock" in sources:
        return {
            "state": "PARTIAL LIVE",
            "message": "Some endpoints are live; unavailable endpoints are using fallback data.",
            "icon": "🟠",
        }
    if sources == {"mock"}:
        return {
            "state": "MOCK",
            "message": "Using offline sample data because live endpoints are unavailable.",
            "icon": "🟡",
        }
    return {
        "state": "PARTIAL DATA",
        "message": "Some endpoint statuses are incomplete.",
        "icon": "ℹ️",
    }


def _contains_mock_data(data: Any) -> bool:
    """Return True when cached data carries the mock sentinel."""
    if isinstance(data, dict):
        return bool(data.get("_mock"))
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return bool(data[0].get("_mock"))
    return False


def _as_dict(item: Any) -> dict[str, Any]:
    """Convert dict-like or object-like API payload items into dictionaries."""
    if isinstance(item, dict):
        return item
    if hasattr(item, "to_dict"):
        return item.to_dict()
    if hasattr(item, "dict"):
        return item.dict()
    if hasattr(item, "__dict__"):
        return vars(item)
    return {"raw": item}


def _first_value(item: dict[str, Any], aliases: tuple[str, ...], default: Any = None) -> Any:
    """Return the first present, non-empty field from a list of aliases."""
    for alias in aliases:
        value = item.get(alias)
        if value not in (None, ""):
            return value
    return default


def _to_int(value: Any, default: int = 0) -> int:
    """Safely convert API values to integers."""
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _build_url(path: str, params: Optional[dict[str, Any]] = None) -> str:
    """
    Build an Arsha API URL with optional query parameters.

    Keeping URL construction in one helper makes it easier to change region,
    language, or endpoint paths later.
    """
    query = f"?{urlencode(params)}" if params else ""
    return f"{ARSHA_BASE_URL}{path}{query}"


def _read_json_url(url: str) -> Any:
    """
    Read JSON from a public Arsha API URL.

    Arsha does not require an API key. If the upstream BDO source is blocked or
    returns invalid data, Arsha usually responds with a JSON error body. This
    helper turns that into a short exception message that the app can display.
    """
    request = Request(url, headers={"User-Agent": "bdo-analytics/phase-1"})
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise ArshaApiError(_format_arsha_error(exc.code, body)) from exc
    except URLError as exc:
        raise ArshaApiError(f"Could not reach Arsha API: {exc.reason}") from exc

    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise ArshaApiError("Arsha API returned a non-JSON response.") from exc


def _format_arsha_error(status_code: int, body: str) -> str:
    """
    Convert an Arsha error response into a readable dashboard message.

    Example: the API may return 500 with a message saying the upstream request
    was probably blocked by Imperva. That is not an API key problem.
    """
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return f"Arsha API returned HTTP {status_code}."

    message = payload.get("message", "No message")
    code = payload.get("code")
    if code:
        return f"Arsha API returned HTTP {status_code} (code {code}): {message}"
    return f"Arsha API returned HTTP {status_code}: {message}"


def _history_from_v1_result(data: Any, item_id: int, source: str) -> dict[str, Any]:
    """
    Convert the v1 history alias into the dashboard's date-to-price mapping.

    The v1 endpoint returns one hyphen-separated price per day, oldest first.
    Arsha currently documents this as roughly 90 days of history.
    """
    if not isinstance(data, dict) or data.get("resultCode") != 0:
        return _normalize_history(data, item_id=item_id, source=source)

    prices = [
        _to_int(price)
        for price in str(data.get("resultMsg", "")).split("-")
        if price
    ]
    today = datetime.now(UTC).date()
    start_date = today - timedelta(days=len(prices) - 1)
    history = {
        (start_date + timedelta(days=index)).isoformat(): price
        for index, price in enumerate(prices)
    }
    return {"_mock": source == "mock", "history": history, "itemId": item_id}


def _normalize_item(
    item: Any,
    *,
    source: str,
    category_id: Optional[str] = None,
    sub_category_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Normalize a raw API or mock item into the dashboard's internal schema.

    The external API can expose different names for the same concept, so this
    function keeps the rest of the app stable by mapping aliases into one shape.
    """
    raw = _as_dict(item)
    main_category = str(_first_value(raw, ("mainCategory", "main_category"), category_id) or "")
    sub_category = str(_first_value(raw, ("subCategory", "sub_category"), sub_category_id) or "")
    item_id = _to_int(_first_value(raw, ("id", "itemId", "item_id", "mainKey", "main_key")))
    sid = _to_int(_first_value(raw, ("sid", "subKey", "sub_key", "enhancementLevel"), 0))
    total_trade_count = _to_int(
        _first_value(raw, ("totalTradeCount", "totalTrades", "total_trades", "totalTrade"), 0)
    )
    trade_count = _to_int(
        _first_value(raw, ("tradeCount", "trade_count", "recentTradeCount"), total_trade_count)
    )

    normalized = {
        "_mock": bool(raw.get("_mock")) or source == "mock",
        "id": item_id,
        "sid": sid,
        "name": _first_value(raw, ("name", "itemName", "item_name"), f"Item {item_id}"),
        "mainCategory": _to_int(main_category),
        "mainCategoryName": CATEGORY_NAMES.get(main_category, main_category or "Unknown"),
        "subCategory": _to_int(sub_category),
        "minPrice": _to_int(
            _first_value(raw, ("minPrice", "basePrice", "base_price", "price", "currentPrice"), 0)
        ),
        "tradeCount": trade_count,
        "currentStock": _to_int(_first_value(raw, ("currentStock", "current_stock", "stock"), 0)),
        "totalTradeCount": total_trade_count,
        "source": source,
    }
    if "priceHistory" in raw:
        normalized["priceHistory"] = raw["priceHistory"]
    return normalized


def _normalize_items(
    items: list[Any],
    *,
    source: str,
    category_id: Optional[str] = None,
    sub_category_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Normalize and de-duplicate a list of raw market items."""
    normalized = [
        _normalize_item(
            item,
            source=source,
            category_id=category_id,
            sub_category_id=sub_category_id,
        )
        for item in items
    ]
    deduped: dict[tuple[int, int], dict[str, Any]] = {}
    for item in normalized:
        deduped[(item["id"], item["sid"])] = item
    return list(deduped.values())


def _apply_item_category_index(
    items: list[dict[str, Any]],
    category_index: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Fill missing category information from an item-id lookup.

    The Hot Items endpoint returns item prices and trade counts, but it does not
    include the Central Market category. The category index comes from the
    regular market list endpoint and lets the Hot Items table show useful names
    instead of ``Unknown``.
    """
    enriched = []
    for item in items:
        updated = item.copy()
        metadata = category_index.get(str(item.get("id")))
        if metadata and updated.get("mainCategoryName") == "Unknown":
            updated["mainCategory"] = metadata["mainCategory"]
            updated["mainCategoryName"] = metadata["mainCategoryName"]
            updated["subCategory"] = metadata["subCategory"]
        elif updated.get("mainCategoryName") == "Unknown":
            updated.update(_infer_category_from_name(str(updated.get("name", ""))))
        enriched.append(updated)
    return enriched


def _infer_category_from_name(name: str) -> dict[str, Any]:
    """
    Infer a useful category for obvious item names not present in the index.

    This is a last-resort display helper. The live API remains the source of
    truth when it provides category metadata, but a few hot-list items such as
    seeds and wagon parts do not appear in the category scan.
    """
    lowered = name.lower()
    if "seed" in lowered or "hypha" in lowered:
        return {"mainCategory": 25, "mainCategoryName": "Seed / Hypha", "subCategory": 0}
    if "fishing rod" in lowered or "float" in lowered:
        return {"mainCategory": 40, "mainCategoryName": "Fishing Gear", "subCategory": 0}
    if name.startswith("[Donkey]") or name.startswith("[Horse]"):
        return {"mainCategory": 65, "mainCategoryName": "Mount Gear", "subCategory": 0}
    if "wagon" in lowered:
        return {"mainCategory": 75, "mainCategoryName": "Wagon Part", "subCategory": 0}
    return {"mainCategory": 0, "mainCategoryName": "Unknown", "subCategory": 0}


def _build_item_category_index(target_ids: set[int]) -> dict[str, dict[str, Any]]:
    """
    Build or refresh an item-id-to-category lookup for specific item IDs.

    This is intentionally cached because scanning Central Market categories
    requires several API calls. The scan stops early once all requested hot-item
    IDs have been found.
    """
    cache_key = "item_category_index"
    cached = _read_cache(cache_key)
    category_index: dict[str, dict[str, Any]] = cached if isinstance(cached, dict) else {}

    missing_ids = {item_id for item_id in target_ids if str(item_id) not in category_index}
    if not missing_ids:
        return category_index

    for main_category, category_name in MARKET_MAIN_CATEGORIES.items():
        for sub_category in range(1, MAX_SUBCATEGORY_SCAN + 1):
            try:
                url = _build_url(
                    f"/v2/{REGION}/GetWorldMarketList",
                    {
                        "mainCategory": main_category,
                        "subCategory": sub_category,
                        "lang": LANGUAGE,
                    },
                )
                data = _read_json_url(url)
            except ArshaApiError:
                # Some category/subcategory combinations do not exist. That is
                # normal while scanning, so skip them quietly.
                continue

            items = data if isinstance(data, list) else [data]
            for raw_item in items:
                item_id = _to_int(_first_value(_as_dict(raw_item), ("id", "itemId", "item_id")))
                if item_id == 0:
                    continue
                category_index[str(item_id)] = {
                    "mainCategory": _to_int(main_category),
                    "mainCategoryName": category_name,
                    "subCategory": sub_category,
                }
                missing_ids.discard(item_id)

            if not missing_ids:
                _write_cache(cache_key, category_index, source="live")
                return category_index

    _write_cache(cache_key, category_index, source="live")
    return category_index


def _normalize_history(data: Any, item_id: int, source: str) -> dict[str, Any]:
    """Normalize supported price-history payload shapes into ``history``."""
    if data is None:
        return {"_mock": source == "mock", "history": {}, "itemId": item_id}

    if isinstance(data, dict) and "history" in data:
        return {**data, "_mock": source == "mock" or bool(data.get("_mock")), "itemId": item_id}

    raw = data
    if isinstance(data, list) and len(data) == 1:
        raw = data[0]
    raw_dict = _as_dict(raw)

    history = raw_dict.get("history") or raw_dict.get("prices") or raw_dict.get("priceHistory")
    if isinstance(history, list):
        converted = {}
        for row in history:
            row_dict = _as_dict(row)
            date = _first_value(row_dict, ("date", "time", "timestamp"))
            price = _first_value(row_dict, ("price", "basePrice", "minPrice"))
            if date is not None and price is not None:
                converted[str(date)] = _to_int(price)
        history = converted

    return {
        "_mock": source == "mock" or bool(raw_dict.get("_mock")),
        "history": history if isinstance(history, dict) else {},
        "itemId": item_id,
    }


# ---------------------------------------------------------------------------
# Mock data — realistic fallback when arsha.io is unreachable
# ---------------------------------------------------------------------------


def _mock_hot_items() -> list[dict]:
    """Return a realistic list of hot/trending items across categories."""
    return [
        {"_mock": True, "id": 9001, "name": "Memory Fragment", "sid": 0, "minPrice": 1750000, "tradeCount": 84200, "mainCategory": 25, "subCategory": 1, "totalTradeCount": 9500000},
        {"_mock": True, "id": 4917, "name": "Black Stone (Weapon)", "sid": 0, "minPrice": 225000, "tradeCount": 62100, "mainCategory": 25, "subCategory": 2, "totalTradeCount": 45000000},
        {"_mock": True, "id": 16001, "name": "Sharp Black Crystal Shard", "sid": 0, "minPrice": 6500000, "tradeCount": 31400, "mainCategory": 25, "subCategory": 1, "totalTradeCount": 12000000},
        {"_mock": True, "id": 4918, "name": "Black Stone (Armor)", "sid": 0, "minPrice": 195000, "tradeCount": 58700, "mainCategory": 25, "subCategory": 2, "totalTradeCount": 42000000},
        {"_mock": True, "id": 16002, "name": "Hard Black Crystal Shard", "sid": 0, "minPrice": 5800000, "tradeCount": 28900, "mainCategory": 25, "subCategory": 1, "totalTradeCount": 11500000},
        {"_mock": True, "id": 721003, "name": "Cron Stone", "sid": 0, "minPrice": 2000000, "tradeCount": 19500, "mainCategory": 25, "subCategory": 3, "totalTradeCount": 8700000},
        {"_mock": True, "id": 44195, "name": "Manos Processing Stone - Metal", "sid": 0, "minPrice": 85000000, "tradeCount": 1200, "mainCategory": 25, "subCategory": 4, "totalTradeCount": 320000},
        {"_mock": True, "id": 9213, "name": "Beer", "sid": 0, "minPrice": 2100, "tradeCount": 125000, "mainCategory": 35, "subCategory": 1, "totalTradeCount": 98000000},
        {"_mock": True, "id": 9801, "name": "Essence of Liquor", "sid": 0, "minPrice": 1600, "tradeCount": 97000, "mainCategory": 35, "subCategory": 2, "totalTradeCount": 65000000},
        {"_mock": True, "id": 9062, "name": "Elixir of Will", "sid": 0, "minPrice": 28000, "tradeCount": 43000, "mainCategory": 45, "subCategory": 1, "totalTradeCount": 18000000},
    ]


def _mock_cooking_items() -> list[dict]:
    """Return realistic Cooking/Alchemy ingredient items."""
    return [
        {"_mock": True, "id": 9213, "name": "Beer", "sid": 0, "minPrice": 2100, "tradeCount": 125000, "currentStock": 340000, "totalTradeCount": 98000000, "mainCategory": 35, "subCategory": 1},
        {"_mock": True, "id": 9801, "name": "Essence of Liquor", "sid": 0, "minPrice": 1600, "tradeCount": 97000, "currentStock": 520000, "totalTradeCount": 65000000, "mainCategory": 35, "subCategory": 2},
        {"_mock": True, "id": 9002, "name": "Vinegar", "sid": 0, "minPrice": 1250, "tradeCount": 85000, "currentStock": 410000, "totalTradeCount": 54000000, "mainCategory": 35, "subCategory": 2},
        {"_mock": True, "id": 9003, "name": "Cream", "sid": 0, "minPrice": 1100, "tradeCount": 72000, "currentStock": 290000, "totalTradeCount": 42000000, "mainCategory": 35, "subCategory": 2},
        {"_mock": True, "id": 9004, "name": "Butter", "sid": 0, "minPrice": 1350, "tradeCount": 63000, "currentStock": 195000, "totalTradeCount": 38000000, "mainCategory": 35, "subCategory": 2},
        {"_mock": True, "id": 9005, "name": "Cheese", "sid": 0, "minPrice": 1450, "tradeCount": 58000, "currentStock": 175000, "totalTradeCount": 35000000, "mainCategory": 35, "subCategory": 2},
        {"_mock": True, "id": 9006, "name": "Flour", "sid": 0, "minPrice": 700, "tradeCount": 110000, "currentStock": 680000, "totalTradeCount": 88000000, "mainCategory": 35, "subCategory": 3},
        {"_mock": True, "id": 9007, "name": "Sugar", "sid": 0, "minPrice": 600, "tradeCount": 105000, "currentStock": 720000, "totalTradeCount": 82000000, "mainCategory": 35, "subCategory": 3},
        {"_mock": True, "id": 9008, "name": "Olive Oil", "sid": 0, "minPrice": 1800, "tradeCount": 48000, "currentStock": 132000, "totalTradeCount": 28000000, "mainCategory": 35, "subCategory": 2},
        {"_mock": True, "id": 9009, "name": "Mineral Water", "sid": 0, "minPrice": 450, "tradeCount": 140000, "currentStock": 950000, "totalTradeCount": 105000000, "mainCategory": 35, "subCategory": 3},
        {"_mock": True, "id": 9062, "name": "Elixir of Will", "sid": 0, "minPrice": 28000, "tradeCount": 43000, "currentStock": 87000, "totalTradeCount": 18000000, "mainCategory": 45, "subCategory": 1},
        {"_mock": True, "id": 9063, "name": "Elixir of Fury", "sid": 0, "minPrice": 32000, "tradeCount": 38000, "currentStock": 64000, "totalTradeCount": 15000000, "mainCategory": 45, "subCategory": 1},
    ]


def _mock_item_history(item_id: int) -> dict:
    """
    Generate 90 days of mock price history for a given item.

    Prices fluctuate randomly around a base value derived from the item ID.
    """
    import random
    random.seed(item_id)  # deterministic per item

    base_price = (item_id % 10000) * 200 + 500
    history = {}
    today = datetime.now(UTC).date()
    for days_ago in range(90, -1, -1):
        date = today - timedelta(days=days_ago)
        # Simulate ±15% daily fluctuation
        noise = random.uniform(-0.15, 0.15)
        price = int(base_price * (1 + noise))
        history[date.isoformat()] = price

    return {"_mock": True, "history": history, "itemId": item_id}


# ---------------------------------------------------------------------------
# API interaction (async core, sync wrappers exposed publicly)
# ---------------------------------------------------------------------------


async def _fetch_hot_items() -> list[dict]:
    """
    Fetch trending/hot items from the BDO EU Central Market.

    Returns cached data if available and fresh, otherwise calls arsha.io.
    Falls back to mock data on any error.
    """
    cache_key = "hot_items"
    cached = _read_cache(cache_key)
    if cached is not None:
        return cached

    try:
        url = _build_url(
            f"/v2/{REGION}/GetWorldMarketHotList",
            {"lang": LANGUAGE},
        )
        data = _read_json_url(url)
        items = data if isinstance(data, list) else [data]
        normalized = _normalize_items(items, source="live")
        if normalized:
            target_ids = {item["id"] for item in normalized if item.get("id")}
            category_index = _build_item_category_index(target_ids)
            enriched = _apply_item_category_index(normalized, category_index)
            _write_cache(cache_key, enriched, source="live")
            return enriched
        error = "Live API returned no hot-item content."
    except Exception as exc:
        # Keep the dashboard usable, but record the error so it is visible in
        # the UI and useful while debugging API or network issues.
        error = f"{type(exc).__name__}: {exc}"
        LOGGER.debug("Failed to fetch hot items from arsha.io: %s", error)

    # Fallback: mock data
    mock = _normalize_items(_mock_hot_items(), source="mock")
    _write_cache(cache_key, mock, source="mock", error=error)
    return mock


async def _fetch_cooking_items() -> list[dict]:
    """
    Fetch items in the Cooking & Alchemy categories from the BDO EU market.

    Tries Cooking (mainCategory=35) first, then appends Alchemy (45).
    Falls back to mock data on any error.
    """
    cache_key = "cooking_items"
    cached = _read_cache(cache_key)
    if cached is not None:
        return cached

    try:
        combined: list[dict] = []
        # Fetch a small configured set of useful subcategories rather than
        # only subcategory 1. This gives a broader Cooking/Alchemy view while
        # keeping the number of API calls controlled.
        for cat, sub_categories in CRAFTING_CATEGORY_SUBCATEGORIES.items():
            for sub_category in sub_categories:
                try:
                    url = _build_url(
                        f"/v2/{REGION}/GetWorldMarketList",
                        {
                            "mainCategory": cat,
                            "subCategory": sub_category,
                            "lang": LANGUAGE,
                        },
                    )
                    data = _read_json_url(url)
                    items = data if isinstance(data, list) else [data]
                    combined.extend(
                        _normalize_items(
                            items,
                            source="live",
                            category_id=cat,
                            sub_category_id=sub_category,
                        )
                    )
                except Exception as exc:
                    LOGGER.debug(
                        "Skipping category %s, subcategory %s: %s",
                        cat,
                        sub_category,
                        exc,
                    )

        if combined:
            _write_cache(cache_key, combined, source="live")
            return combined
        error = "Live API returned no Cooking/Alchemy content for the configured subcategories."
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        LOGGER.debug("Failed to fetch Cooking/Alchemy items from arsha.io: %s", error)

    mock = _normalize_items(_mock_cooking_items(), source="mock")
    _write_cache(cache_key, mock, source="mock", error=error)
    return mock


async def _fetch_item_history(item_id: int, enhancement_level: int = 0) -> dict:
    """
    Fetch price history for a single item from the BDO EU market.

    Args:
        item_id: The numeric BDO item ID.
        enhancement_level: Enhancement level (0 = base).

    Returns:
        A dict with at least a ``history`` key mapping dates to prices.
    """
    cache_key = f"history_{item_id}_{enhancement_level}"
    cached = _read_cache(cache_key)
    if cached is not None:
        return cached

    try:
        url = _build_url(
            f"/v1/{REGION}/history",
            {"id": item_id, "sid": enhancement_level},
        )
        data = _history_from_v1_result(_read_json_url(url), item_id=item_id, source="live")
        if data.get("history"):
            _write_cache(cache_key, data, source="live")
            return data
        error = f"Live API returned no price-history content for item {item_id}."
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        LOGGER.debug("Failed to fetch item history from arsha.io: %s", error)

    mock = _normalize_history(_mock_item_history(item_id), item_id=item_id, source="mock")
    _write_cache(cache_key, mock, source="mock", error=error)
    return mock


# ---------------------------------------------------------------------------
# Public synchronous API — call these from Streamlit or any sync context
# ---------------------------------------------------------------------------


def get_hot_items() -> list[dict]:
    """
    Get the current list of trending items across all categories.

    Returns:
        A list of dicts, each representing a hot item with keys like
        ``id``, ``name``, ``minPrice``, ``tradeCount``, etc.
    """
    return asyncio.run(_fetch_hot_items())


def get_cooking_items() -> list[dict]:
    """
    Get items in the Cooking and Alchemy categories.

    Returns:
        A list of dicts with item details including price and stock info.
    """
    return asyncio.run(_fetch_cooking_items())


def get_item_history(item_id: int, enhancement_level: int = 0) -> dict:
    """
    Get the price history for a specific item.

    Args:
        item_id: The numeric BDO item ID.
        enhancement_level: Enhancement level (default 0 = base).

    Returns:
        A dict with a ``history`` key mapping date strings to prices.
    """
    return asyncio.run(_fetch_item_history(item_id, enhancement_level))
