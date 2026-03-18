import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import date

from data import get_earnings_date, TICKER_MAPPING


def _process_radar_row(row, ticker_data):
    """Process a single radar row using pre-fetched batch data."""
    t = row['Ticker']
    c = row['Cost']
    stock_type = "💰" if row['Type'] == 'Holding' else "👀"

    e_date = get_earnings_date(t)

    dist_pct = 0
    ema_info = "計算中..."
    p = 0

    df_t = ticker_data.get(t)
    if df_t is not None and len(df_t) > 200:
        p = df_t['Close'].iloc[-1]
        ema200 = df_t['EMA_200'].iloc[-1]
        prev_ema200 = df_t['EMA_200'].iloc[-2]
        prev_p = df_t['Close'].iloc[-2]

        dist_pct = ((p - ema200) / ema200) * 100
        prev_dist_pct = ((prev_p - prev_ema200) / prev_ema200) * 100

        if abs(dist_pct) > abs(prev_dist_pct):
            trend = "↗️ 擴張" if dist_pct > 0 else "↘️ 遠離"
        else:
            trend = "➡️ 修正" if dist_pct > 0 else "⤴️ 回歸"

        ema_info = f"{dist_pct:+.1f}% ({trend})"

    pl_pct = ((p - c) / c * 100) if c > 0 else 0

    days_left = 999
    e_str = "N/A"
    if e_date:
        try:
            days_left = (e_date - date.today()).days
            e_str = f"{e_date.strftime('%m/%d')} ({days_left}d)"
        except: pass

    return {
        "狀態": stock_type,
        "代碼": t,
        "最新價": p,
        "報酬率 (%)": pl_pct if row['Type'] == 'Holding' else None,
        "EMA 200 乖離 (趨勢)": ema_info,
        "下次財報 (倒數)": e_str,
        "_days": days_left,
        "_dist": dist_pct
    }


@st.cache_data(ttl=300)
def _batch_download(tickers_tuple):
    """Batch download all tickers in one yf.download call (thread-safe)."""
    tickers_list = list(tickers_tuple)
    # Map display tickers to yfinance tickers
    yf_tickers = [TICKER_MAPPING.get(t.upper(), t) for t in tickers_list]

    try:
        raw = yf.download(yf_tickers, period="2y", progress=False, group_by='ticker')
    except:
        return {}

    result = {}
    for orig_t, yf_t in zip(tickers_list, yf_tickers):
        try:
            if len(yf_tickers) == 1:
                df = raw.copy()
            else:
                df = raw[yf_t].copy()
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.dropna(how='all')
            if df.empty:
                continue
            df = df.reset_index()
            df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
            df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
            df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
            exp1 = df['Close'].ewm(span=12, adjust=False).mean()
            exp2 = df['Close'].ewm(span=26, adjust=False).mean()
            df['MACD'] = exp1 - exp2
            df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
            df['Hist'] = df['MACD'] - df['Signal']
            result[orig_t] = df
        except:
            continue
    return result


def render_radar(portfolio_df):
    """Render the Macro Radar view with batch data fetching."""
    st.markdown("### 📡 全球戰術雷達 (Global Tactical Radar)")
    st.caption("同步掃描「持倉」與「關注」標的，監控 EMA 200 位階與財報倒數。")

    all_targets = portfolio_df
    if all_targets.empty:
        st.info("尚無紀錄，請至「庫存管理」新增！")
        return

    with st.spinner("📡 批次掃描中 (Batch Fetch)..."):
        # Batch download all tickers at once (thread-safe, cacheable)
        all_tickers = tuple(all_targets['Ticker'].tolist())
        ticker_data = _batch_download(all_tickers)

        radar_data = []
        for _, row in all_targets.iterrows():
            try:
                result = _process_radar_row(row, ticker_data)
                radar_data.append(result)
            except:
                radar_data.append({
                    "狀態": "❌",
                    "代碼": row['Ticker'],
                    "最新價": 0,
                    "報酬率 (%)": None,
                    "EMA 200 乖離 (趨勢)": "Error",
                    "下次財報 (倒數)": "N/A",
                    "_days": 999,
                    "_dist": 0
                })

        if radar_data:
            radar_df = pd.DataFrame(radar_data).sort_values("_days")

            def style_radar(styler):
                def color_earnings(val):
                    if '(' in str(val):
                        try:
                            days = int(str(val).split('(')[1].split('d')[0])
                            if days <= 7: return 'background-color: #8B0000; color: white'
                            if days <= 14: return 'background-color: #B8860B; color: white'
                        except: pass
                    return ''

                def color_ema(val):
                    if '+' in str(val): return 'color: #00FF00;'
                    if '-' in str(val): return 'color: #FF4136;'
                    return ''

                styler.applymap(color_earnings, subset=["下次財報 (倒數)"])
                styler.applymap(color_ema, subset=["EMA 200 乖離 (趨勢)"])
                styler.format({
                    "最新價": "${:.2f}",
                    "報酬率 (%)": lambda x: f"{x:+.2f}%" if pd.notnull(x) else "---"
                })
                return styler

            styled_df = radar_df.drop(columns=["_days", "_dist"]).style.pipe(style_radar)
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
