"""
Best-seller scoring and anomaly detection for BDO market items.

Accepts a pandas DataFrame of market items and enriches it with:
- Volume Score (0–100)
- Price Stability Score (0–100)
- Turnover Rate
- Composite Best Seller Score
- Anomaly Flag
"""

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Constants — score weights and thresholds
# ---------------------------------------------------------------------------

VOLUME_WEIGHT = 0.5
STABILITY_WEIGHT = 0.3
TURNOVER_WEIGHT = 0.2

ANOMALY_STD_THRESHOLD = 2.0   # flag if price deviates > 2 σ from 30-day MA
MOVING_AVG_WINDOW = 30        # days for the anomaly moving average


def enrich_items(df: pd.DataFrame) -> pd.DataFrame:
    """
    Enrich a DataFrame of market items with analytics columns.

    Expects the input DataFrame to have at least these columns:
        - tradeCount   (int/float) — recent trade volume
        - minPrice     (int/float) — current listing price

    Optional columns used if present:
        - currentStock (int/float) — items currently listed
        - priceHistory (list[int/float]) — recent price samples

    Args:
        df: Raw market item DataFrame.

    Returns:
        A copy of *df* with these columns appended:
        volumeScore, priceStability, turnoverRate, turnoverScore,
        bestSellerScore, hasPriceHistory, anomaly, anomalyStatus
    """
    if df.empty:
        # Return an empty frame with the expected extra columns
        for col in (
            "volumeScore",
            "priceStability",
            "turnoverRate",
            "turnoverScore",
            "bestSellerScore",
            "hasPriceHistory",
            "anomaly",
            "anomalyStatus",
        ):
            df[col] = pd.Series(dtype="float64")
        return df

    result = df.copy()

    # --- 1. Volume Score (0–100) -------------------------------------------
    tc = result["tradeCount"].astype(float)
    tc_min, tc_max = tc.min(), tc.max()
    if tc_max > tc_min:
        result["volumeScore"] = ((tc - tc_min) / (tc_max - tc_min) * 100).round(2)
    else:
        # All items have the same trade count — assign midpoint
        result["volumeScore"] = 50.0

    # --- 2. Price Stability Score (0–100) ----------------------------------
    # This metric needs multiple historical price points. If history is missing,
    # leave the score blank instead of inventing a neutral value.
    if "priceHistory" in result.columns:
        def _stability(history: list) -> float:
            """Compute stability from a list of price samples."""
            if not history or len(history) < 2:
                return np.nan
            arr = np.array(history, dtype=float)
            mean = arr.mean()
            if mean == 0:
                return np.nan
            cv = arr.std() / mean  # coefficient of variation
            # Lower CV → higher stability. Cap CV at 1.0 for normalisation.
            return round(max(0, (1 - min(cv, 1.0)) * 100), 2)

        result["priceStability"] = result["priceHistory"].apply(_stability)
        result["hasPriceHistory"] = result["priceHistory"].apply(
            lambda history: isinstance(history, list) and len(history) >= 2
        )
    else:
        result["priceStability"] = np.nan
        result["hasPriceHistory"] = False

    # --- 3. Turnover Rate --------------------------------------------------
    if "currentStock" in result.columns:
        avg_daily = tc / 30  # rough proxy: tradeCount is ~monthly
        avg_daily = avg_daily.replace(0, np.nan)
        result["turnoverRate"] = (
            result["currentStock"].astype(float) / avg_daily
        ).round(2)
    else:
        result["turnoverRate"] = np.nan

    # --- 4. Composite Best Seller Score ------------------------------------
    # Invert turnover: lower turnover = faster selling = higher score
    if result["turnoverRate"].notna().any():
        tr = result["turnoverRate"].copy()
        tr_min, tr_max = tr.min(), tr.max()
        if tr_max > tr_min:
            # Invert so that low turnover → high score
            result["turnoverScore"] = ((tr_max - tr) / (tr_max - tr_min) * 100).round(2)
        else:
            result["turnoverScore"] = 50.0
    else:
        result["turnoverScore"] = np.nan

    # Reweight the composite per row based only on metrics we actually have.
    # Example: if price history is missing, Volume and Turnover split the score.
    weighted_score = result["volumeScore"] * VOLUME_WEIGHT
    available_weight = pd.Series(VOLUME_WEIGHT, index=result.index, dtype=float)

    stability_available = result["priceStability"].notna()
    weighted_score = weighted_score + result["priceStability"].fillna(0) * STABILITY_WEIGHT
    available_weight = available_weight + stability_available.astype(float) * STABILITY_WEIGHT

    turnover_available = result["turnoverScore"].notna()
    weighted_score = weighted_score + result["turnoverScore"].fillna(0) * TURNOVER_WEIGHT
    available_weight = available_weight + turnover_available.astype(float) * TURNOVER_WEIGHT

    result["bestSellerScore"] = (weighted_score / available_weight).round(2)

    # --- 5. Anomaly Flag ---------------------------------------------------
    if "priceHistory" in result.columns:
        def _is_anomaly(row) -> bool:
            """Check if current price deviates >2σ from 30-day moving avg."""
            history = row.get("priceHistory")
            price = row.get("minPrice", 0)
            if not history or len(history) < MOVING_AVG_WINDOW:
                return False
            recent = np.array(history[-MOVING_AVG_WINDOW:], dtype=float)
            ma = recent.mean()
            std = recent.std()
            if std == 0:
                return False
            return abs(price - ma) > ANOMALY_STD_THRESHOLD * std

        result["anomaly"] = result.apply(_is_anomaly, axis=1)
        result["anomalyStatus"] = np.where(
            result["hasPriceHistory"],
            np.where(result["anomaly"], "Anomaly", "Normal"),
            "Insufficient history",
        )
    else:
        result["anomaly"] = False
        result["anomalyStatus"] = "Insufficient history"

    return result
