"""
BDO Market API wrapper with caching and mock fallback.

Connects to the BDO EU Central Market via arsha.io (community proxy).
All responses are cached as JSON files with a 15-minute TTL.
If the API is unreachable, realistic mock data is returned instead.
"""

import asyncio
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache"
CACHE_TTL_SECONDS = 15 * 60  # 15 minutes

# BDO category IDs
COOKING_MAIN_CATEGORY = "35"   # Cooking in arsha.io V2 category mapping
ALCHEMY_MAIN_CATEGORY = "45"   # Alchemy

# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


def _cache_path(key: str) -> Path:
    """Return the file path for a given cache key."""
    return CACHE_DIR / f"{key}.json"


def _read_cache(key: str) -> Optional[dict]:
    """
    Read cached data if it exists and is fresher than CACHE_TTL_SECONDS.

    Args:
        key: A unique string identifying this cached response.

    Returns:
        The cached data as a dict/list, or None if stale or missing.
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

    return wrapper.get("data")


def _write_cache(key: str, data: Any) -> None:
    """
    Write data to a JSON cache file with the current timestamp.

    Args:
        key: A unique string identifying this cached response.
        data: The API response data to cache.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    wrapper = {"cached_at": time.time(), "data": data}
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
    data = _read_cache(key)
    if data is None:
        return False
    # Mock payloads are tagged with "_mock": True at the top level
    if isinstance(data, dict) and data.get("_mock"):
        return False
    if isinstance(data, list) and data and isinstance(data[0], dict) and data[0].get("_mock"):
        return False
    return True


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
    today = datetime.utcnow().date()
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
        from bdomarket import ArshaMarket, MarketRegion, ApiVersion, Locale

        async with ArshaMarket(
            region=MarketRegion.EU,
            apiversion=ApiVersion.V2,
            language=Locale.English,
        ) as market:
            response = await market.get_world_market_hot_list()

        if response.success and response.content:
            data = response.content if isinstance(response.content, list) else [response.content]
            _write_cache(cache_key, data)
            return data
    except Exception:
        pass  # fall through to mock

    # Fallback: mock data
    mock = _mock_hot_items()
    _write_cache(cache_key, mock)
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
        from bdomarket import ArshaMarket, MarketRegion, ApiVersion, Locale

        combined: list[dict] = []
        async with ArshaMarket(
            region=MarketRegion.EU,
            apiversion=ApiVersion.V2,
            language=Locale.English,
        ) as market:
            for cat in (COOKING_MAIN_CATEGORY, ALCHEMY_MAIN_CATEGORY):
                resp = await market.get_world_market_list(main_category=cat, sub_category="1")
                if resp.success and resp.content:
                    items = resp.content if isinstance(resp.content, list) else [resp.content]
                    combined.extend(items)

        if combined:
            _write_cache(cache_key, combined)
            return combined
    except Exception:
        pass

    mock = _mock_cooking_items()
    _write_cache(cache_key, mock)
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
        from bdomarket import ArshaMarket, MarketRegion, ApiVersion, Locale

        async with ArshaMarket(
            region=MarketRegion.EU,
            apiversion=ApiVersion.V2,
            language=Locale.English,
        ) as market:
            resp = await market.get_market_price_info(
                ids=[str(item_id)],
                sids=[str(enhancement_level)],
                convertdate=True,
            )

        if resp.success and resp.content:
            data = resp.content if isinstance(resp.content, dict) else {"history": resp.content}
            _write_cache(cache_key, data)
            return data
    except Exception:
        pass

    mock = _mock_item_history(item_id)
    _write_cache(cache_key, mock)
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
