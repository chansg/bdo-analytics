# Sprint 03 - Data Health & Table Polish

This sprint improves how the dashboard explains live data reliability and makes
the main tables easier to scan. The important product change is that the app no
longer treats data as simply live or mock when the real state can be mixed.

## Scope

- Add a `PARTIAL LIVE` dashboard state for mixed live/mock endpoint results.
- Add a `Data Health` panel with endpoint status, last fetch time, and fallback
  detail.
- Format silver values with commas.
- Format score columns to two decimal places.
- Display missing numeric values as `N/A` instead of `None`.
- Add automated tests for the data health summary logic.

## Automated Checks

Run from the repository root:

```bash
python -m pytest
```

Expected result:

```text
8 passed
```

## Manual Test Plan

Use this checklist to sign off the sprint in the pull request.

### 1. Data Health Banner Is Accurate

1. Open a terminal in the repository root.
2. Run `streamlit run app.py`.
3. Open the dashboard in the browser.
4. Click `Refresh Data`.

Expected result:

- If all loaded endpoints are live, the banner says `LIVE`.
- If some endpoints are live and some use fallback data, the banner says
  `PARTIAL LIVE`.
- If all loaded endpoints use fallback data, the banner says `MOCK`.

### 2. Data Health Panel Shows Endpoint Details

1. Open the `Data Health` expander under the status banner.
2. Review the endpoint rows.

Expected result:

- `Hot Items` appears as an endpoint.
- `Cooking / Alchemy` appears as an endpoint.
- Each row shows a status, last fetch timestamp, and fallback detail or `N/A`.
- Fallback detail explains upstream Arsha/Imperva failures when present.

### 3. Hot Items Table Is Easy To Scan

1. Open the `Hot Items Leaderboard` tab.
2. Review the price and trade count columns.

Expected result:

- `Current Price` uses comma separators.
- `Trade Count` uses comma separators.
- `Anomaly Status` remains readable.

### 4. Cooking / Alchemy Table Is Easy To Scan

1. Open the `Cooking / Alchemy Browser` tab.
2. Review numeric columns.

Expected result:

- `Price` uses comma separators.
- Score columns show two decimal places.
- Missing values show `N/A`, not `None`.
- Best Seller Score colour coding still works.

### 5. Existing Launch Flow Still Works

1. Stop the dashboard.
2. From the repository root, run `python app.py`.
3. From the repository root, run `streamlit run app.py`.

Expected result:

- `python app.py` shows the friendly Streamlit launch instruction.
- `streamlit run app.py` starts the dashboard normally.

## Sign-Off

- [ ] Manual tests completed by Chanveer
- [ ] Approved to merge
