# CLAUDE.md — 戰術狙擊鏡 Project Context

## Project Overview
**戰術狙擊鏡 (Technical Sniper)** is a Streamlit-based stock monitoring dashboard for tracking portfolio holdings and watchlist stocks with technical analysis, institutional ownership data, and earnings alerts.

## Tech Stack
- **Framework**: Streamlit (Python)
- **Data Source**: yfinance (Yahoo Finance API)
- **Charts**: Plotly (dark theme, candlestick + subplots)
- **Cloud Storage**: Google Apps Script (Google Sheets as backend)
- **Deployment**: Streamlit Community Cloud (auto-deploys from `main` branch)
- **No local development** — all code changes go through GitHub directly

## Architecture
- `app.py` — single-file Streamlit app, everything lives here
- `requirements.txt` — pip dependencies for Streamlit Cloud
- Portfolio data is stored in Google Sheets via a GAS webhook (`GAS_URL`)
- Data is cached using `@st.cache_data` with TTLs (300s for prices, 86400s for fundamentals)

## Key Features
- **Macro Radar**: parallel-fetched overview of all holdings/watchlist with EMA 200 divergence and earnings countdown
- **Single Stock View**: candlestick chart with EMA 20/50/200, MACD, support/resistance detection
- **Buyback Scanner**: share count trend vs price (護城河掃描)
- **Whale Sonar**: top institutional holders from 13F filings (巨鯨聲納)
- **AI Judgment Badges**: rule-based tactical signals (EMA position, S/R proximity, earnings warning, short squeeze potential)

## Coding Conventions
- UI labels and user-facing text: **Traditional Chinese (繁體中文)**
- Code comments and variable names: **English**
- Single-file architecture — do NOT split into multiple modules
- Use `@st.cache_data` for all API calls with appropriate TTL
- Plotly charts use `template="plotly_dark"`
- All yfinance calls should handle empty/missing data gracefully (try/except, null checks)
- Bare `except: pass` is used intentionally for resilience — acceptable in this project
- Keep the GAS_URL as-is (it's a public Apps Script endpoint, not a secret)

## Ticker Mapping
These shortcuts are supported in the app:
- `SOX` → `^SOX`, `NDX` → `^NDX`, `DJI` → `^DJI`, `GSPC` → `^GSPC`
- `VIX` → `^VIX`, `BTC` → `BTC-USD`, `ETH` → `ETH-USD`

## Testing
- No automated tests — this is a personal dashboard tool
- To verify changes: deploy to Streamlit Cloud and check the UI manually
- Make sure the Macro Radar loads without errors (parallel fetch)
- Make sure S/R levels render on the candlestick chart

## Common Tasks
- **Adding a new indicator**: compute it in `get_stock_data()`, add to chart in the `tab_tech` section
- **Adding a new info card**: add a new `st.container(border=True)` block in the 2x2 grid area
- **Adding a new judgment badge**: append to the `judgments` list with 🟢/🔴/🟡 prefix
- **Adding a new data tab**: add to the `st.tabs()` call and create a `with tab_xxx:` block

## Dependencies
All listed in `requirements.txt`. When adding a new library, always update `requirements.txt` — Streamlit Cloud installs from it on every deploy.
