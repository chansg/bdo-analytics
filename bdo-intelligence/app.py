"""
BDO Market Intelligence Dashboard — EU

Streamlit dashboard for browsing trending items, Cooking/Alchemy market data,
and price history on the Black Desert Online EU Central Market.

Run with:
    streamlit run app.py
"""

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------------------
# Ensure local packages are importable when running via `streamlit run app.py`
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent))

from api.market import (
    clear_cache,
    get_cooking_items,
    get_hot_items,
    get_item_history,
    is_using_live_data,
)
from analytics.best_sellers import enrich_items

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BEST_SELLER_GREEN = 70
BEST_SELLER_AMBER = 40

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="BDO Market Intelligence — EU",
    page_icon="⚔️",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    if st.button("🔄 Refresh Data"):
        clear_cache()
        st.cache_data.clear()
        st.rerun()

    st.caption(f"Last refreshed: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")

    with st.expander("ℹ️ Score Definitions"):
        st.markdown(
            """
**Volume Score (0–100)**
How much an item is traded relative to others.
Higher = more popular.

**Price Stability (0–100)**
Based on the coefficient of variation of recent prices.
Higher = more predictable pricing.

**Turnover Rate**
Current stock ÷ average daily volume.
Lower = items sell faster (more liquid).

**Best Seller Score**
Weighted composite:
- 50 % Volume
- 30 % Stability
- 20 % Turnover (inverted)

**Anomaly Flag**
True when the current price deviates > 2 standard deviations
from its 30-day moving average — could signal a crash or spike.
"""
        )


# ---------------------------------------------------------------------------
# Data loaders (cached by Streamlit to avoid redundant API calls)
# ---------------------------------------------------------------------------


@st.cache_data(ttl=900, show_spinner="Fetching hot items…")
def load_hot_items() -> pd.DataFrame:
    """Load and return the hot items leaderboard as a DataFrame."""
    items = get_hot_items()
    if not items:
        return pd.DataFrame()
    df = pd.DataFrame(items)
    return enrich_items(df)


@st.cache_data(ttl=900, show_spinner="Fetching Cooking / Alchemy items…")
def load_cooking_items() -> pd.DataFrame:
    """Load and return Cooking/Alchemy items as an enriched DataFrame."""
    items = get_cooking_items()
    if not items:
        return pd.DataFrame()
    df = pd.DataFrame(items)
    return enrich_items(df)


@st.cache_data(ttl=900, show_spinner="Fetching price history…")
def load_item_history(item_id: int) -> dict:
    """Load price history for a single item."""
    return get_item_history(item_id)


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("BDO Market Intelligence — EU")
st.caption("Cooking & Alchemy · Live Data via arsha.io")

# Data source indicator
live = is_using_live_data("hot_items") or is_using_live_data("cooking_items")
if live:
    st.success("🟢 LIVE — data sourced from arsha.io", icon="🟢")
else:
    st.warning("🟡 MOCK — using offline sample data", icon="🟡")


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_hot, tab_cooking, tab_history = st.tabs(
    ["🔥 Hot Items Leaderboard", "🍳 Cooking / Alchemy Browser", "📈 Price History"]
)

# ----- Tab 1: Hot Items Leaderboard ----------------------------------------
with tab_hot:
    hot_df = load_hot_items()
    if hot_df.empty:
        st.info("No hot-item data available.")
    else:
        # Build a display table
        display = hot_df.copy()

        # Add a rank column
        display.insert(0, "Rank", range(1, len(display) + 1))

        # Pick columns that exist
        cols_wanted = ["Rank", "name", "mainCategory", "minPrice", "tradeCount", "anomaly"]
        cols_present = [c for c in cols_wanted if c in display.columns]
        display = display[cols_present]

        # Rename for readability
        rename_map = {
            "name": "Item Name",
            "mainCategory": "Category",
            "minPrice": "Current Price",
            "tradeCount": "Trade Count",
            "anomaly": "Anomaly",
        }
        display = display.rename(columns=rename_map)

        # Highlight anomaly rows
        def _highlight_anomaly(row):
            if row.get("Anomaly"):
                return ["background-color: #fff3cd"] * len(row)
            return [""] * len(row)

        styled = display.style.apply(_highlight_anomaly, axis=1)
        st.dataframe(styled, use_container_width=True, hide_index=True)


# ----- Tab 2: Cooking / Alchemy Browser -----------------------------------
with tab_cooking:
    cook_df = load_cooking_items()
    if cook_df.empty:
        st.info("No Cooking / Alchemy data available.")
    else:
        # Optional sub-category filter
        if "subCategory" in cook_df.columns:
            sub_cats = ["All"] + sorted(cook_df["subCategory"].dropna().unique().tolist())
            chosen = st.selectbox("Filter by sub-category", sub_cats)
            if chosen != "All":
                cook_df = cook_df[cook_df["subCategory"] == chosen]

        # Columns for display
        cols_wanted = [
            "name", "minPrice", "volumeScore", "priceStability",
            "turnoverRate", "bestSellerScore", "anomaly",
        ]
        cols_present = [c for c in cols_wanted if c in cook_df.columns]
        display = cook_df[cols_present].copy()

        rename_map = {
            "name": "Item Name",
            "minPrice": "Price",
            "volumeScore": "Volume Score",
            "priceStability": "Price Stability",
            "turnoverRate": "Turnover Rate",
            "bestSellerScore": "Best Seller Score",
            "anomaly": "Anomaly",
        }
        display = display.rename(columns=rename_map)

        # Default sort by Best Seller Score descending
        if "Best Seller Score" in display.columns:
            display = display.sort_values("Best Seller Score", ascending=False)

        # Colour-code the Best Seller Score column
        def _colour_score(val):
            if pd.isna(val):
                return ""
            if val > BEST_SELLER_GREEN:
                return "background-color: #d4edda"  # green
            if val >= BEST_SELLER_AMBER:
                return "background-color: #fff3cd"  # amber
            return "background-color: #f8d7da"       # red

        styled = display.style
        if "Best Seller Score" in display.columns:
            styled = styled.map(_colour_score, subset=["Best Seller Score"])
        st.dataframe(styled, use_container_width=True, hide_index=True)


# ----- Tab 3: Price History ------------------------------------------------
with tab_history:
    cook_all = load_cooking_items()
    if cook_all.empty or "name" not in cook_all.columns:
        st.info("No items available for price history.")
    else:
        # Build an item selector from names
        item_options = cook_all[["id", "name"]].drop_duplicates()
        item_map = dict(zip(item_options["name"], item_options["id"]))
        selected_name = st.selectbox("Select an item", sorted(item_map.keys()))
        selected_id = int(item_map[selected_name])

        history_data = load_item_history(selected_id)
        history = history_data.get("history", {})

        if not history:
            st.info("No price history available for this item.")
        else:
            # Build a time-series DataFrame
            hist_df = (
                pd.DataFrame(
                    list(history.items()), columns=["date", "price"]
                )
                .assign(date=lambda d: pd.to_datetime(d["date"]))
                .sort_values("date")
                .reset_index(drop=True)
            )
            hist_df["price"] = hist_df["price"].astype(float)
            hist_df["7d_ma"] = hist_df["price"].rolling(window=7, min_periods=1).mean()

            # Metric cards
            col1, col2, col3 = st.columns(3)
            col1.metric("Min Price", f"{hist_df['price'].min():,.0f}")
            col2.metric("Max Price", f"{hist_df['price'].max():,.0f}")
            col3.metric("Current Price", f"{hist_df['price'].iloc[-1]:,.0f}")

            # Plotly chart
            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=hist_df["date"],
                    y=hist_df["price"],
                    mode="lines",
                    name="Price",
                    line=dict(color="#1f77b4"),
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=hist_df["date"],
                    y=hist_df["7d_ma"],
                    mode="lines",
                    name="7-day MA",
                    line=dict(color="#ff7f0e", dash="dash"),
                )
            )
            fig.update_layout(
                title=f"Price History — {selected_name}",
                xaxis_title="Date",
                yaxis_title="Price (Silver)",
                hovermode="x unified",
                template="plotly_white",
            )
            st.plotly_chart(fig, use_container_width=True)
