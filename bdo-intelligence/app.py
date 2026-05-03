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
from streamlit.runtime.scriptrunner import get_script_run_ctx

# ---------------------------------------------------------------------------
# Ensure local packages are importable when running via `streamlit run app.py`
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Streamlit apps need to be launched by Streamlit, not plain Python.
# Without this guard, `python app.py` produces a long list of internal
# Streamlit runtime warnings that are confusing while learning the project.
if get_script_run_ctx(suppress_warning=True) is None:
    print("\nThis is a Streamlit dashboard.")
    print("Start it with this command instead:\n")
    print("    streamlit run app.py\n")
    print("If you are in the project root, use:")
    print("    streamlit run bdo-intelligence/app.py\n")
    sys.exit(0)

from api.market import (
    clear_cache,
    get_cooking_items,
    get_data_status,
    get_hot_items,
    get_item_history,
    summarize_data_health,
)
from analytics.best_sellers import enrich_items
from services.watchlist import (
    add_to_watchlist,
    load_watchlist,
    make_item_key,
    remove_from_watchlist,
    save_watchlist,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BEST_SELLER_GREEN = 70
BEST_SELLER_AMBER = 40
EXPORT_MIME_TYPE = "text/csv"

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

    with st.expander("ℹ️ Score Definitions"):
        st.markdown(
            """
**Volume Score (0–100)**
How much an item is traded relative to others.
Higher = more popular.

**Price Stability (0–100)**
Based on the coefficient of variation of recent prices.
Higher = more predictable pricing. Blank means price history is unavailable.

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
from its 30-day moving average. "Insufficient history" means the dashboard
does not have enough historical prices to make that call yet.
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


def _latest_fetch_time(*statuses: dict) -> str:
    """
    Return the latest available fetch timestamp from status dictionaries.

    This is more accurate than showing the current page render time because
    Streamlit may reuse cached data without making a fresh API call.
    """
    fetched_at_values = [status.get("fetched_at") for status in statuses if status.get("fetched_at")]
    if not fetched_at_values:
        return "No cached data yet"
    return max(fetched_at_values)


def _status_label(source: str) -> str:
    """
    Convert the cached source value into a short UI label.

    Keeping this in one helper means the banner, health table, and future pages
    use the same wording.
    """
    labels = {
        "live": "Live",
        "mock": "Mock fallback",
        "unknown": "Not loaded",
    }
    return labels.get(source, str(source).title())


def _show_data_status(endpoint_statuses: list[dict]) -> None:
    """
    Show whether the dashboard is using live data or mock fallback data.

    The API layer stores this metadata whenever it writes cache files.
    """
    health = summarize_data_health(endpoint_statuses)
    banner_text = f"{health['state']} — {health['message']}"
    if health["state"] == "LIVE":
        st.success(banner_text, icon=health["icon"])
    elif health["state"] in {"PARTIAL LIVE", "MOCK"}:
        st.warning(banner_text, icon=health["icon"])
    else:
        st.info(banner_text, icon=health["icon"])

    with st.expander("Data Health", expanded=health["state"] != "LIVE"):
        rows = []
        for status in endpoint_statuses:
            rows.append(
                {
                    "Endpoint": status["label"],
                    "Status": _status_label(status.get("source", "unknown")),
                    "Last Fetch": status.get("fetched_at") or "N/A",
                    "Fallback Detail": status.get("error") or "N/A",
                }
            )
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


def _format_styled_table(styled, formatters: dict) -> object:
    """
    Apply consistent table formatting.

    The dashboard tables are easier to scan when silver values use commas,
    scores use two decimals, and missing values display as N/A.
    """
    return styled.format(formatters, na_rep="N/A")


def _add_item_keys(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add stable watchlist keys to a market DataFrame.

    Streamlit re-runs the script after every click. A stable ``itemKey`` lets
    the app remember "Beer +0" even when row positions or sorting changes.
    """
    if df.empty or "id" not in df.columns:
        return df.copy()

    keyed = df.copy()
    if "sid" not in keyed.columns:
        keyed["sid"] = 0

    keyed["itemKey"] = [
        make_item_key(item_id, sid)
        for item_id, sid in zip(keyed["id"], keyed["sid"], strict=False)
    ]
    return keyed


def _build_item_catalog(*frames: pd.DataFrame) -> pd.DataFrame:
    """
    Build one item picker source from all loaded market tables.

    Cooking/Alchemy rows are passed first because they usually contain richer
    score columns than Hot Items. Duplicate item keys keep that richer row.
    """
    prepared = []
    for source_name, frame in frames:
        if frame.empty:
            continue
        copy = _add_item_keys(frame)
        copy["watchlistSource"] = source_name
        prepared.append(copy)

    if not prepared:
        return pd.DataFrame()

    catalog = pd.concat(prepared, ignore_index=True)
    catalog = catalog.drop_duplicates(subset=["itemKey"], keep="first")
    catalog["watchlistLabel"] = catalog.apply(_watchlist_label_from_row, axis=1)
    return catalog.sort_values("watchlistLabel").reset_index(drop=True)


def _watchlist_label_from_row(row: pd.Series) -> str:
    """
    Return a readable picker label for one market item row.

    The label includes category and item key so two same-name items can still be
    told apart if enhancement levels are added later.
    """
    category = row.get("mainCategoryName") or "Unknown"
    name = row.get("name") or f"Item {row.get('id', 'Unknown')}"
    return f"{name} — {category} ({row.get('itemKey', 'unknown')})"


def _labels_for_keys(catalog: pd.DataFrame, item_keys: list[str]) -> dict[str, str]:
    """
    Map saved watchlist keys to human-readable labels.

    Some saved keys may not be present in the current live API response. Those
    still get a fallback label so the user can remove them if needed.
    """
    if catalog.empty:
        return {key: key for key in item_keys}

    label_by_key = dict(zip(catalog["itemKey"], catalog["watchlistLabel"], strict=False))
    return {key: label_by_key.get(key, key) for key in item_keys}


def _filter_watchlist_items(catalog: pd.DataFrame, item_keys: list[str]) -> pd.DataFrame:
    """
    Return catalog rows that match the saved watchlist keys.

    The categorical ordered dtype keeps the table in the same order the player
    added items instead of whatever order the market API returns today.
    """
    if catalog.empty or not item_keys:
        return pd.DataFrame()

    watched = catalog[catalog["itemKey"].isin(item_keys)].copy()
    watched["itemKey"] = pd.Categorical(watched["itemKey"], categories=item_keys, ordered=True)
    return watched.sort_values("itemKey").reset_index(drop=True)


def _csv_bytes(df: pd.DataFrame) -> bytes:
    """
    Convert a DataFrame into downloadable CSV bytes.

    Keeping this tiny helper central means every export button behaves the same
    way and is easy to test manually.
    """
    return df.to_csv(index=False).encode("utf-8")


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("BDO Market Intelligence — EU")
st.caption("Cooking & Alchemy · Live Data via arsha.io")

# Load the two main datasets before showing source status. This keeps the
# LIVE/MOCK badge tied to the actual data on screen.
hot_df = _add_item_keys(load_hot_items())
cook_df = _add_item_keys(load_cooking_items())
hot_status = get_data_status("hot_items")
cooking_status = get_data_status("cooking_items")
endpoint_statuses = [
    {"label": "Hot Items", **hot_status},
    {"label": "Cooking / Alchemy", **cooking_status},
]
_show_data_status(endpoint_statuses)
st.sidebar.caption(f"Last data fetch: {_latest_fetch_time(hot_status, cooking_status)}")

# The catalog powers the sidebar picker and the Watchlist tab. Cooking/Alchemy
# is passed first because those rows include the best-seller analytics.
item_catalog = _build_item_catalog(
    ("Cooking / Alchemy", cook_df),
    ("Hot Items", hot_df),
)
watchlist_keys = load_watchlist()

with st.sidebar.expander("⭐ Watchlist", expanded=True):
    if item_catalog.empty:
        st.caption("No market items are loaded yet.")
    else:
        option_by_label = dict(
            zip(item_catalog["watchlistLabel"], item_catalog["itemKey"], strict=False)
        )
        selected_label = st.selectbox("Add item", list(option_by_label.keys()))

        if st.button("Add to Watchlist"):
            watchlist_keys = add_to_watchlist(watchlist_keys, option_by_label[selected_label])
            save_watchlist(watchlist_keys)
            st.success("Item added.")
            st.rerun()

    if watchlist_keys:
        labels_by_key = _labels_for_keys(item_catalog, watchlist_keys)
        remove_labels = st.multiselect("Remove item(s)", list(labels_by_key.values()))
        key_by_label = {label: key for key, label in labels_by_key.items()}

        if st.button("Remove Selected"):
            selected_keys = [key_by_label[label] for label in remove_labels]
            watchlist_keys = remove_from_watchlist(watchlist_keys, selected_keys)
            save_watchlist(watchlist_keys)
            st.success("Watchlist updated.")
            st.rerun()

    st.caption(f"{len(watchlist_keys)} saved item(s)")


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_hot, tab_cooking, tab_history, tab_watchlist = st.tabs(
    [
        "🔥 Hot Items Leaderboard",
        "🍳 Cooking / Alchemy Browser",
        "📈 Price History",
        "⭐ Watchlist",
    ]
)

# ----- Tab 1: Hot Items Leaderboard ----------------------------------------
with tab_hot:
    if hot_df.empty:
        st.info("No hot-item data available.")
    else:
        # Build a display table
        display = hot_df.copy()

        # Add a rank column
        display.insert(0, "Rank", range(1, len(display) + 1))

        # Pick columns that exist
        cols_wanted = [
            "Rank",
            "name",
            "mainCategoryName",
            "minPrice",
            "tradeCount",
            "anomalyStatus",
        ]
        cols_present = [c for c in cols_wanted if c in display.columns]
        display = display[cols_present]

        # Rename for readability
        rename_map = {
            "name": "Item Name",
            "mainCategoryName": "Category",
            "minPrice": "Current Price",
            "tradeCount": "Trade Count",
            "anomalyStatus": "Anomaly Status",
        }
        display = display.rename(columns=rename_map)

        # Highlight anomaly rows
        def _highlight_anomaly(row):
            if row.get("Anomaly Status") == "Anomaly":
                return ["background-color: #fff3cd"] * len(row)
            return [""] * len(row)

        styled = display.style.apply(_highlight_anomaly, axis=1)
        styled = _format_styled_table(
            styled,
            {
                "Current Price": "{:,.0f}",
                "Trade Count": "{:,.0f}",
            },
        )
        st.dataframe(styled, width="stretch", hide_index=True)
        st.download_button(
            "Download Hot Items CSV",
            data=_csv_bytes(display),
            file_name="bdo_hot_items_eu.csv",
            mime=EXPORT_MIME_TYPE,
        )


# ----- Tab 2: Cooking / Alchemy Browser -----------------------------------
with tab_cooking:
    if cook_df.empty:
        st.info("No Cooking / Alchemy data available.")
    else:
        filtered_cook_df = cook_df.copy()

        # Optional sub-category filter
        if "subCategory" in cook_df.columns:
            sub_cats = ["All"] + sorted(cook_df["subCategory"].dropna().unique().tolist())
            chosen = st.selectbox("Filter by sub-category", sub_cats)
            if chosen != "All":
                filtered_cook_df = filtered_cook_df[filtered_cook_df["subCategory"] == chosen]

        # Columns for display
        cols_wanted = [
            "name", "minPrice", "volumeScore", "priceStability",
            "turnoverRate", "bestSellerScore", "anomalyStatus",
        ]
        cols_present = [c for c in cols_wanted if c in filtered_cook_df.columns]
        display = filtered_cook_df[cols_present].copy()

        rename_map = {
            "name": "Item Name",
            "minPrice": "Price",
            "volumeScore": "Volume Score",
            "priceStability": "Price Stability",
            "turnoverRate": "Turnover Rate",
            "bestSellerScore": "Best Seller Score",
            "anomalyStatus": "Anomaly Status",
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
        styled = _format_styled_table(
            styled,
            {
                "Price": "{:,.0f}",
                "Volume Score": "{:.2f}",
                "Price Stability": "{:.2f}",
                "Turnover Rate": "{:.2f}",
                "Best Seller Score": "{:.2f}",
            },
        )
        st.dataframe(styled, width="stretch", hide_index=True)
        st.download_button(
            "Download Cooking / Alchemy CSV",
            data=_csv_bytes(display),
            file_name="bdo_cooking_alchemy_eu.csv",
            mime=EXPORT_MIME_TYPE,
        )


# ----- Tab 3: Price History ------------------------------------------------
with tab_history:
    cook_all = cook_df
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
            st.plotly_chart(fig, width="stretch")


# ----- Tab 4: Watchlist ----------------------------------------------------
with tab_watchlist:
    watched_df = _filter_watchlist_items(item_catalog, watchlist_keys)

    if not watchlist_keys:
        st.info("Your watchlist is empty. Add items from the sidebar to track them here.")
    elif watched_df.empty:
        st.warning(
            "Your saved watchlist items are not present in the currently loaded market data."
        )
    else:
        missing_keys = sorted(set(watchlist_keys) - set(watched_df["itemKey"].astype(str)))
        if missing_keys:
            st.warning(
                "Some saved items are not present in the current market response: "
                + ", ".join(missing_keys)
            )

        cols_wanted = [
            "name",
            "watchlistSource",
            "mainCategoryName",
            "minPrice",
            "tradeCount",
            "currentStock",
            "volumeScore",
            "bestSellerScore",
            "anomalyStatus",
        ]
        cols_present = [column for column in cols_wanted if column in watched_df.columns]
        display = watched_df[cols_present].copy()

        rename_map = {
            "name": "Item Name",
            "watchlistSource": "Source",
            "mainCategoryName": "Category",
            "minPrice": "Price",
            "tradeCount": "Trade Count",
            "currentStock": "Current Stock",
            "volumeScore": "Volume Score",
            "bestSellerScore": "Best Seller Score",
            "anomalyStatus": "Anomaly Status",
        }
        display = display.rename(columns=rename_map)

        st.metric("Watched Items", len(watched_df))
        styled = _format_styled_table(
            display.style,
            {
                "Price": "{:,.0f}",
                "Trade Count": "{:,.0f}",
                "Current Stock": "{:,.0f}",
                "Volume Score": "{:.2f}",
                "Best Seller Score": "{:.2f}",
            },
        )
        st.dataframe(styled, width="stretch", hide_index=True)
        st.download_button(
            "Download Watchlist CSV",
            data=_csv_bytes(display),
            file_name="bdo_watchlist_eu.csv",
            mime=EXPORT_MIME_TYPE,
        )
