# Sprint 01 - Phase 1.5 Stabilization

This sprint strengthens the Phase 1 marketplace dashboard before new capstone
features are added. The goal is to make the dashboard clearer about where its
data came from, safer around live API changes, and more honest when a metric
does not have enough data behind it yet.

## Scope

- Normalize live and mock market items into one dashboard-friendly schema.
- Store cache metadata such as source, fetch time, and fallback errors.
- Fetch multiple configured Cooking/Alchemy subcategories instead of only one.
- Show live/mock/fallback state after the dashboard data has loaded.
- Mark missing price history as unavailable instead of using neutral values.
- Add automated tests for normalization and analytics behavior.

## Automated Checks

Run from the repository root:

```bash
python -m pytest
```

Expected result:

```text
4 passed
```

## Manual Test Plan

Use this checklist to sign off the sprint in the pull request.

### 1. Dashboard Starts

1. Open a terminal in the repository root.
2. Run `python -m streamlit run bdo-intelligence/app.py`.
3. Open `http://localhost:8501`.

Expected result:

- The dashboard loads without a Python traceback.
- The page title contains `BDO Market Intelligence` and `EU`.
- The sidebar shows `Last data fetch`.

### 2. Data Source Status Is Clear

1. Click `Refresh Data` in the sidebar.
2. Wait for the dashboard tables to reload.
3. Check the status message below the title.

Expected result:

- The page shows either `LIVE - data sourced from arsha.io` or
  `MOCK - using offline sample data`.
- If mock data is used because the API failed, `Latest API fallback details`
  is available and shows the reason.

### 3. Hot Items Leaderboard Still Works

1. Open the `Hot Items Leaderboard` tab.
2. Review the table columns.

Expected result:

- Rows are visible.
- The table includes item name, category, current price, trade count, and
  anomaly status.
- Any anomaly row is highlighted.

### 4. Cooking / Alchemy Browser Uses Honest Metrics

1. Open the `Cooking / Alchemy Browser` tab.
2. Sort by `Best Seller Score`.
3. Review the `Price Stability` and `Anomaly Status` columns.

Expected result:

- Rows are visible.
- `Best Seller Score` is populated.
- `Price Stability` shows `N/A` where price history is unavailable.
- `Anomaly Status` says `Insufficient history` when the app cannot calculate it.

### 5. Price History Chart Still Works

1. Open the `Price History` tab.
2. Select an item from the dropdown.

Expected result:

- Min, max, and current price metric cards render.
- A Plotly line chart renders.
- The chart includes a price line and a 7-day moving average line.

## Sign-Off

- [ ] Manual tests completed by Chanveer
- [ ] Approved to merge
