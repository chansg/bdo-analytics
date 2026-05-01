import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = PROJECT_ROOT / "bdo-intelligence"
sys.path.insert(0, str(APP_ROOT))

from analytics.best_sellers import enrich_items  # noqa: E402


def test_missing_price_history_is_marked_as_unavailable():
    """Missing history should not produce fake stability or anomaly scores."""
    df = pd.DataFrame(
        [
            {"name": "Low Volume", "tradeCount": 10, "minPrice": 100, "currentStock": 50},
            {"name": "High Volume", "tradeCount": 100, "minPrice": 120, "currentStock": 30},
        ]
    )

    result = enrich_items(df)

    assert result["priceStability"].isna().all()
    assert result["hasPriceHistory"].eq(False).all()
    assert result["anomaly"].eq(False).all()
    assert result["anomalyStatus"].eq("Insufficient history").all()
    assert result["bestSellerScore"].notna().all()


def test_price_history_enables_stability_and_anomaly_detection():
    """Enough history should produce a stability score and flag price spikes."""
    normal_history = [100, 102, 101, 103, 99] * 8
    spike_history = list(range(90, 120))
    df = pd.DataFrame(
        [
            {
                "name": "Stable Item",
                "tradeCount": 100,
                "minPrice": 101,
                "currentStock": 50,
                "priceHistory": normal_history,
            },
            {
                "name": "Spiking Item",
                "tradeCount": 50,
                "minPrice": 150,
                "currentStock": 40,
                "priceHistory": spike_history,
            },
        ]
    )

    result = enrich_items(df)

    assert result["priceStability"].notna().all()
    assert result["hasPriceHistory"].eq(True).all()
    assert result.loc[result["name"] == "Spiking Item", "anomaly"].iloc[0]
    assert result.loc[result["name"] == "Spiking Item", "anomalyStatus"].iloc[0] == "Anomaly"
