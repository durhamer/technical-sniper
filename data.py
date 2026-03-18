import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import date

TICKER_MAPPING = {
    "SOX": "^SOX", "NDX": "^NDX", "DJI": "^DJI", "GSPC": "^GSPC",
    "VIX": "^VIX", "BTC": "BTC-USD", "ETH": "ETH-USD",
}


@st.cache_data(ttl=300)
def get_stock_data(ticker, period="2y"):
    target_ticker = TICKER_MAPPING.get(ticker.upper(), ticker)
    try:
        df = yf.download(target_ticker, period=period, progress=False)
        if df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.reset_index()
        df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
        df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
        df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2
        df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['Hist'] = df['MACD'] - df['Signal']
        return df
    except:
        return None


@st.cache_data(ttl=86400)
def get_shares_data(ticker):
    if "^" in ticker or "USD" in ticker:
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
def get_earnings_date(ticker):
    if "^" in ticker or "USD" in ticker:
        return None
    try:
        tk = yf.Ticker(ticker)
        cal = tk.calendar
        if cal is not None and 'Earnings Date' in cal:
            dates = cal['Earnings Date']
            if isinstance(dates, list) and len(dates) > 0:
                return dates[0]
    except:
        pass
    return None


@st.cache_data(ttl=86400)
def get_smart_money_data(ticker):
    if "^" in ticker or "USD" in ticker:
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
    if "^" in ticker or "USD" in ticker:
        return None
    try:
        df = yf.Ticker(ticker).institutional_holders
        if df is not None and not df.empty:
            return df
    except:
        pass
    return None
