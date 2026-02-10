import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- 1. 頁面設定 ---
st.set_page_config(page_title="戰術狙擊鏡 v1.0", layout="wide")
st.title("🎯 戰術狙擊鏡 (Tactical Sniper)")

# --- 2. 側邊欄：控制台 ---
with st.sidebar:
    st.header("⚙️ 參數設定")
    
    # 輸入股票代碼
    ticker = st.text_input("輸入美股代碼", value="SPY").upper()
    
    # 選擇時間範圍
    time_range = st.selectbox("時間範圍", ["1 Year", "6 Months", "3 Years", "5 Years"], index=0)
    
    st.divider()
    
    st.subheader("均線設定 (EMA)")
    show_ema20 = st.checkbox("顯示 EMA 20 (短線慣性)", value=True)
    show_ema50 = st.checkbox("顯示 EMA 50 (機構防線)", value=True)
    show_ema200 = st.checkbox("顯示 EMA 200 (牛熊分界)", value=True)

# --- 3. 數據處理函數 ---
def get_data(ticker, period):
    # 將選項轉換為 yfinance 格式
    period_map = {"1 Year": "1y", "6 Months": "6mo", "3 Years": "3y", "5 Years": "5y"}
    p = period_map.get(period, "1y")
    
    try:
        df = yf.download(ticker, period=p, progress=False)
        
        # 如果是 MultiIndex (新版 yfinance 可能會出現)，將其扁平化
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        df = df.reset_index()
        return df
    except Exception as e:
        st.error(f"無法抓取數據: {e}")
        return None

def calculate_indicators(df):
    # 計算 EMA
    df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
    return df

# --- 4. 主程式邏輯 ---
if ticker:
    # 1. 抓取數據
    raw_df = get_data(ticker, time_range)
    
    if raw_df is not None and not raw_df.empty:
        # 2. 計算指標
        df = calculate_indicators(raw_df)
        
        # 3. 取得最新報價資訊
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        change = latest['Close'] - prev['Close']
        pct_change = (change / prev['Close']) * 100
        
        # 顯示頂部數據卡片
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(f"{ticker} 收盤價", f"{latest['Close']:.2f}", f"{change:.2f} ({pct_change:.2f}%)")
        c2.metric("EMA 20", f"{latest['EMA_20']:.2f}", delta_color="off")
        c3.metric("EMA 50", f"{latest['EMA_50']:.2f}", delta_color="off")
        c4.metric("EMA 200", f"{latest['EMA_200']:.2f}", delta_color="off")

        # 4. 繪製互動式圖表 (Plotly)
        fig = go.Figure()

        # A. 畫 K 線 (Candlestick)
        fig.add_trace(go.Candlestick(
            x=df['Date'],
            open=df['Open'],
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            name="Price"
        ))

        # B. 畫均線 (根據勾選狀態)
        if show_ema20:
            fig.add_trace(go.Scatter(x=df['Date'], y=df['EMA_20'], name="EMA 20", line=dict(color='green', width=1.5)))
        
        if show_ema50:
            fig.add_trace(go.Scatter(x=df['Date'], y=df['EMA_50'], name="EMA 50", line=dict(color='orange', width=2)))
            
        if show_ema200:
            fig.add_trace(go.Scatter(x=df['Date'], y=df['EMA_200'], name="EMA 200", line=dict(color='red', width=2.5)))

        # C. 圖表優化設定
        fig.update_layout(
            title=f"{ticker} - 技術分析圖表",
            yaxis_title="Price",
            xaxis_rangeslider_visible=False, # 隱藏底部滑桿，增加可視空間
            height=700,
            hovermode="x unified",
            # 讓背景變成專業的深色模式 (雖然 Streamlit 會自動適應，但這樣設定更保險)
            template="plotly_dark"
        )

        st.plotly_chart(fig, use_container_width=True)

    else:
        st.warning("找不到該股票數據，請確認代碼是否正確。")
