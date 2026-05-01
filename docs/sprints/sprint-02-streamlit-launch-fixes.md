# Sprint 02 - Streamlit Launch Fixes

This sprint cleans up confusing terminal output seen when the dashboard is
started with `python app.py` instead of Streamlit. The aim is to make beginner
mistakes easier to recover from and keep the console focused on useful messages.

## Scope

- Add a friendly direct-launch guard for `python app.py`.
- Add a repository-root launcher so `streamlit run app.py` works from the
  project root.
- Replace deprecated `use_container_width=True` calls with `width="stretch"`.
- Replace the `bdomarket` wrapper path with direct Arsha API calls.
- Remove the unused `bdomarket` dependency from requirements.
- Improve API fallback messages when live data is unavailable.
- Fix GitHub issue #2 by showing one status dot in the live/mock banner.
- Keep existing automated tests passing.

## Automated Checks

Run from the repository root:

```bash
python -m pytest
```

Expected result:

```text
5 passed
```

## Manual Test Plan

Use this checklist to sign off the sprint in the pull request.

### 1. Direct Python Launch Is Friendly

1. Open a terminal in the repository root.
2. Run `python app.py`.

Expected result:

- The app prints a short message explaining that this is a Streamlit dashboard.
- The output shows `streamlit run app.py`.
- The command exits without a long `missing ScriptRunContext` warning flood.

### 2. Streamlit Launch Still Works

1. Open a terminal in the repository root.
2. Run `streamlit run app.py`.
3. Open `http://localhost:8501`.

Expected result:

- The dashboard loads in the browser.
- The page shows `BDO Market Intelligence - EU`.
- The sidebar still shows the last data fetch timestamp.
- The live or mock status banner shows only one status dot.

### 3. Nested Streamlit Launch Still Works

1. Open a terminal in the repository root.
2. Run `streamlit run bdo-intelligence/app.py`.
3. Open `http://localhost:8501`.

Expected result:

- The dashboard loads in the browser.
- The behavior matches the root-level launch command.

### 4. Width Deprecation Warning Is Gone

1. Keep the dashboard running from `streamlit run app.py`.
2. Open each dashboard tab.
3. Watch the terminal output.

Expected result:

- The terminal does not show `Please replace use_container_width with width`.
- Tables and charts still stretch across the available page width.

### 5. API Fallback Messages Are Understandable

1. Click `Refresh Data`.
2. Check the data source banner and fallback details if mock data is used.
3. Watch the terminal output.

Expected result:

- If live data works, the app shows the live data banner.
- If live data is unavailable, the app still loads mock data.
- Any fallback detail is short enough to understand what failed.
- The terminal does not print the `bdomarket is up to date` banner.

### 6. Status Banner Does Not Duplicate Icons

1. Open the dashboard in the browser.
2. Check the live/mock status banner below the page subtitle.

Expected result:

- The live banner text says `LIVE` and has one green dot.
- The mock banner text says `MOCK` and has one warning dot.
- There are no duplicated or overlapping dot icons.

## Sign-Off

- [ ] Manual tests completed by Chanveer
- [ ] Approved to merge
