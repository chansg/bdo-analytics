# Sprint 04 - Hot Item Category Enrichment

This sprint improves the Hot Items leaderboard by replacing `Unknown` category
values with useful Central Market category names.

## Scope

- Build a cached item-id-to-category lookup from the Arsha market category
  endpoint.
- Enrich live Hot Items rows with category metadata before they reach the UI.
- Keep existing category labels when the source row already has a useful value.
- Add automated tests for the enrichment helper.

## Automated Checks

Run from the repository root:

```bash
python -m pytest
```

Expected result:

```text
11 passed
```

## Manual Test Plan

Use this checklist to sign off the sprint in the pull request.

### 1. Hot Items Category Column Is Useful

1. Open a terminal in the repository root.
2. Run `streamlit run app.py`.
3. Open the `Hot Items Leaderboard` tab.
4. Click `Refresh Data`.

Expected result:

- The Category column no longer shows `Unknown` for every live hot item.
- Common rows show useful labels such as `Magic Crystal`, `Material`,
  `Accessory`, `Armor`, or another Central Market category.
- If Arsha blocks the live Hot Items endpoint, mock fallback rows should still
  show useful categories instead of `Unknown`.

### 2. Hot Items Table Still Loads If Enrichment Is Partial

1. Keep the dashboard open after refreshing data.
2. Review the Hot Items table.

Expected result:

- The Hot Items table still renders even if a small number of rows cannot be
  matched to category metadata.
- Any unmatched rows may show `Unknown`, but this should be the exception, not
  the whole table.

### 3. Data Health Still Works

1. Open the `Data Health` expander.
2. Review endpoint status rows.

Expected result:

- `Hot Items` appears in the endpoint list.
- `Cooking / Alchemy` appears in the endpoint list.
- The dashboard state remains `LIVE`, `PARTIAL LIVE`, or `MOCK` as appropriate.

### 4. Existing Table Formatting Still Works

1. Review `Current Price` and `Trade Count` in Hot Items.
2. Review score columns in Cooking / Alchemy.

Expected result:

- Silver and trade count values use comma separators.
- Score columns still use two decimal places.
- Missing values still display as `N/A`.

## Sign-Off

- [ ] Manual tests completed by Chanveer
- [ ] Approved to merge
