import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import date

from config import (
    EMA_FAST, EMA_MID, EMA_SLOW,
    MACD_FAST, MACD_SLOW, MACD_SIGNAL,
    SR_ROLLING_WINDOW, SR_PROXIMITY_PCT,
)

TICKER_MAPPING = {
    "SOX": "^SOX", "NDX": "^NDX", "DJI": "^DJI", "GSPC": "^GSPC",
    "VIX": "^VIX", "BTC": "BTC-USD", "ETH": "ETH-USD",
}


def _is_index_or_crypto(ticker):
    return "^" in ticker or "USD" in ticker


@st.cache_data(ttl=300)
def _fetch_stock_data(ticker, period="2y"):
    """Internal cached fetch — raises on failure so Streamlit won't cache None."""
    target_ticker = TICKER_MAPPING.get(ticker.upper(), ticker)
    df = yf.download(target_ticker, period=period, progress=False)
    if df.empty:
        raise LookupError(f"No data for {ticker}")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.reset_index()
    df['EMA_20'] = df['Close'].ewm(span=EMA_FAST, adjust=False).mean()
    df['EMA_50'] = df['Close'].ewm(span=EMA_MID, adjust=False).mean()
    df['EMA_200'] = df['Close'].ewm(span=EMA_SLOW, adjust=False).mean()
    exp1 = df['Close'].ewm(span=MACD_FAST, adjust=False).mean()
    exp2 = df['Close'].ewm(span=MACD_SLOW, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal'] = df['MACD'].ewm(span=MACD_SIGNAL, adjust=False).mean()
    df['Hist'] = df['MACD'] - df['Signal']
    return df


def get_stock_data(ticker, period="2y"):
    """Public wrapper — returns None on failure (never cached as None)."""
    try:
        return _fetch_stock_data(ticker, period)
    except:
        return None


@st.cache_data(ttl=86400)
def get_shares_data(ticker):
    if _is_index_or_crypto(ticker):
        return None, None
    try:
        tk = yf.Ticker(ticker)
        try:
            bs = tk.quarterly_balance_sheet
            if bs.empty:
                bs = tk.balance_sheet
            share_row = None
            possible_names = ['Ordinary Shares Number', 'Share Issued']
            for name in possible_names:
                if name in bs.index:
                    share_row = bs.loc[name]
                    break
            if share_row is not None:
                shares_df = pd.DataFrame(share_row).sort_index()
                shares_df.columns = ['Shares']
                shares_df.index = pd.to_datetime(shares_df.index)
                if len(shares_df) >= 2:
                    latest = shares_df['Shares'].iloc[-1]
                    prev = shares_df['Shares'].iloc[-5] if len(shares_df) >= 5 else shares_df['Shares'].iloc[0]
                    yoy_change = ((latest - prev) / prev) * 100
                    return shares_df, yoy_change
        except:
            pass
        info = tk.info
        if info.get('sharesOutstanding'):
            return None, 0.0
        return None, None
    except:
        return None, None


@st.cache_data(ttl=86400)
def _fetch_earnings_date(ticker):
    """Internal cached fetch — raises on failure so None is never cached."""
    if _is_index_or_crypto(ticker):
        return None  # Intentional None for indices/crypto — safe to cache
    tk = yf.Ticker(ticker)
    cal = tk.calendar
    if cal is None:
        raise LookupError(f"No calendar for {ticker}")
    # cal can be a dict OR a DataFrame depending on yfinance version
    if isinstance(cal, dict):
        dates = cal.get('Earnings Date', [])
    elif isinstance(cal, pd.DataFrame):
        if 'Earnings Date' in cal.columns:
            dates = cal['Earnings Date'].tolist()
        elif 'Earnings Date' in cal.index:
            dates = cal.loc['Earnings Date'].tolist()
        else:
            dates = []
    else:
        dates = []
    if dates and len(dates) > 0:
        return dates[0]
    raise LookupError(f"No earnings date for {ticker}")


def get_earnings_date(ticker):
    """Public wrapper — returns None on failure (never cached as None)."""
    try:
        return _fetch_earnings_date(ticker)
    except:
        return None


@st.cache_data(ttl=86400)
def get_smart_money_data(ticker):
    if _is_index_or_crypto(ticker):
        return None, None
    try:
        info = yf.Ticker(ticker).info
        i = info.get('heldPercentInstitutions')
        s = info.get('shortPercentOfFloat')
        return (i * 100) if i is not None else None, (s * 100) if s is not None else None
    except:
        return None, None


@st.cache_data(ttl=86400)
def get_institutional_holders(ticker):
    if _is_index_or_crypto(ticker):
        return None
    try:
        df = yf.Ticker(ticker).institutional_holders
        if df is not None and not df.empty:
            return df
    except:
        pass
    return None


def find_support_resistance(df, window=SR_ROLLING_WINDOW, proximity_pct=SR_PROXIMITY_PCT):
    """Find key S/R levels using rolling pivot highs/lows."""
    try:
        highs = df['High'].rolling(window, center=True).max()
        lows = df['Low'].rolling(window, center=True).min()

        pivot_highs = df.loc[df['High'] == highs, 'High'].unique()
        pivot_lows = df.loc[df['Low'] == lows, 'Low'].unique()

        all_levels = sorted(set(list(pivot_highs) + list(pivot_lows)))

        # Cluster nearby levels by proximity
        clustered = []
        for level in all_levels:
            if np.isnan(level):
                continue
            merged = False
            for i, (cl, count) in enumerate(clustered):
                if abs(level - cl) / cl < proximity_pct / 100:
                    clustered[i] = ((cl * count + level) / (count + 1), count + 1)
                    merged = True
                    break
            if not merged:
                clustered.append((level, 1))

        # Sort by touch count (strength)
        clustered.sort(key=lambda x: x[1], reverse=True)
        levels = [c[0] for c in clustered]

        current_price = df['Close'].iloc[-1]
        supports = sorted([l for l in levels if l < current_price], reverse=True)[:2]
        resistances = sorted([l for l in levels if l > current_price])[:2]

        return supports, resistances
    except:
        return [], []
