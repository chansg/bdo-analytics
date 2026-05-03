# Sprint 05 — Watchlist and CSV Export

## Objective

Add a lightweight personal workflow on top of the market dashboard: users can save items to a local watchlist, review those watched items in their own tab, and export market tables as CSV files for further analysis.

## Changes Delivered

- Added local watchlist persistence in `bdo-intelligence/services/watchlist.py`.
- Ignored `bdo-intelligence/data/watchlist.json` so personal tracked items are not committed to GitHub.
- Added a sidebar Watchlist control for adding and removing items from the currently loaded market data.
- Added a new Watchlist tab showing saved items with price, volume, stock, score, and anomaly context.
- Added CSV downloads for Hot Items, Cooking/Alchemy, and Watchlist tables.
- Stopped the Cooking/Alchemy subcategory filter from mutating the shared DataFrame used by Price History.
- Updated README feature notes and project structure.

## Automated Verification

Run from the project root:

```powershell
python -m pytest
```

Expected result:

```text
14 passed
```

## Manual Sign-Off Checks

Run the app:

```powershell
streamlit run app.py
```

Then verify:

- The sidebar shows a Watchlist expander with an item selector.
- Add an item from the sidebar and confirm the saved item count increases.
- Open the Watchlist tab and confirm the added item appears in the table.
- Remove the item from the sidebar and confirm it disappears after the app reruns.
- Click **Download Hot Items CSV** and confirm a CSV file downloads.
- Click **Download Cooking / Alchemy CSV** and confirm a CSV file downloads.
- Add at least one item again, click **Download Watchlist CSV**, and confirm the CSV contains only watched items.
- Change the Cooking/Alchemy sub-category filter, then open Price History and confirm the item selector still has Cooking/Alchemy items available.

## Notes for Future Development

- The watchlist currently stores item keys only. Future sprints can add alert thresholds, target buy/sell prices, or notes per item without changing the table workflow.
- The CSV exports are intentionally simple snapshots. Future analysis modules can reuse the same display DataFrames for richer export formats.
