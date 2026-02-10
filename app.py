import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# --- 0. 戰情室資料庫 (User Portfolio) ---
# 這是你的「永久儲存區」，請直接在這裡修改你的持倉與關注清單
# 格式：'代碼': {'cost': 成本價} (若為關注股，cost 設為 None)

PORTFOLIO = {
    # --- 💰 已持倉 (Holdings) ---
    'NVDA': {'cost': 450.00, 'type': 'holding'},
    'TSLA': {'cost': 220.50, 'type': 'holding'},
    'AMD':  {'cost': 110.00, 'type': 'holding'},
    'MSFT': {'cost': 350.00, 'type': 'holding'},
    
    # --- 👀 關注中 (Watchlist) ---
    'AAPL': {'cost': None, 'type': 'watchlist'},
    'PLTR': {'cost': None, 'type': 'watchlist'},
    'COIN': {'cost': None, 'type': 'watchlist'},
    'SMCI': {'cost': None, 'type': 'watchlist'},
}

# --- 1. 頁面設定 ---
st.set_page_config(page_title="戰術狙擊鏡 v2.0", layout="wide")
st.title("🎯 戰術狙擊鏡 (Tactical Sniper)")

# --- 2. 數據處理函數 ---
@st.cache_data(ttl=600) # 快取 10 分鐘，避免每次切換都重抓
def get_data(ticker, period="1y"):
    try:
        df = yf.download(ticker, period=period, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.reset_index()
        # 計算均線
        df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
        df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
        df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
        return df
    except Exception as e:
        return None

# --- 3. 側邊欄：戰術導航 ---
with st.sidebar:
    st.header("🗂️ 投資組合導航")
    
    # 分類
    holdings = [k for k, v in PORTFOLIO.items() if v['type'] == 'holding']
    watchlist = [k for k, v in PORTFOLIO.items() if v['type'] == 'watchlist']
    
    # 選擇器 UX：使用 Radio Button 加上表情符號，更有感
    selection_mode = st.radio("檢視模式", ["💰 持倉庫存", "👀 觀察清單", "🔍 手動搜尋"])
    
    selected_ticker = None
    cost_basis = None
    
    if selection_mode == "💰 持倉庫存":
        selected_ticker = st.selectbox("選擇持倉", holdings)
        if selected_ticker:
            cost_basis = PORTFOLIO[selected_ticker]['cost']
            st.caption(f"🎯 你的成本: ${cost_basis}")
            
    elif selection_mode == "👀 觀察清單":
        selected_ticker = st.selectbox("選擇關注", watchlist)
        
    else: # 手動搜尋
        selected_ticker = st.text_input("輸入代碼 (例如 SPY)", "SPY").upper()

    st.divider()
    st.subheader("⚙️ 圖表參數")
    time_range = st.select_slider("時間範圍", options=["3mo", "6mo", "1y", "3y", "5y"], value="1y")
    show_ema = st.multiselect("顯示均線", ["EMA 20", "EMA 50", "EMA 200"], default=["EMA 20", "EMA 50", "EMA 200"])

# --- 4. 主程式邏輯 ---
if selected_ticker:
    # 抓取數據
    df = get_data(selected_ticker, time_range)
    
    if df is not None and not df.empty:
        # 取得最新數據
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        price = latest['Close']
        change = price - prev['Close']
        pct_change = (change / prev['Close']) * 100
        
        # --- 頂部戰情卡片 ---
        c1, c2, c3, c4 = st.columns(4)
        
        # 卡片 1: 現價
        c1.metric(f"{selected_ticker} 現價", f"{price:.2f}", f"{change:.2f} ({pct_change:.2f}%)")
        
        # 卡片 2: 損益試算 (如果是持倉)
        if cost_basis:
            pl_amount = price - cost_basis
            pl_pct = (pl_amount / cost_basis) * 100
            # 根據賺賠變色
            color = "normal" if pl_amount > 0 else "inverse"
            c2.metric("💰 帳面損益", f"{pl_pct:+.2f}%", f"{pl_amount:+.2f}", delta_color=color)
        else:
            c2.metric("EMA 20 強度", f"{latest['EMA_20']:.2f}")

        c3.metric("EMA 50", f"{latest['EMA_50']:.2f}")
        c4.metric("EMA 200", f"{latest['EMA_200']:.2f}")

        # --- 繪製 K 線圖 ---
        fig = go.Figure()

        # A. K 線
        fig.add_trace(go.Candlestick(
            x=df['Date'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
            name="Price"
        ))

        # B. 成本線 (Killer Feature)
        if cost_basis:
            fig.add_hline(
                y=cost_basis, 
                line_dash="dash", 
                line_color="yellow", 
                line_width=2,
                annotation_text=f"成本: ${cost_basis}", 
                annotation_position="top right"
            )
            # 畫出成本背景區 (讓你感覺現在是在水上還是水下)
            # 這裡用一個簡單的邏輯：如果現價 > 成本，填綠色；反之填紅色 (進階可選)

        # C. 均線
        colors = {'EMA 20': '#00FF00', 'EMA 50': '#FFA500', 'EMA 200': '#FF0000'}
        for ema_name in show_ema:
            col_name = ema_name.replace(" ", "_")
            fig.add_trace(go.Scatter(
                x=df['Date'], y=df[col_name], name=ema_name,
                line=dict(color=colors[ema_name], width=1.5 if '20' in ema_name else 2)
            ))

        # D. 設定
        fig.update_layout(
            height=700,
            hovermode="x unified",
            xaxis_rangeslider_visible=False,
            template="plotly_dark",
            title=f"{selected_ticker} 戰術分析 ({'獲利中 🚀' if cost_basis and price > cost_basis else '監控中 👀'})",
            margin=dict(l=20, r=20, t=50, b=20)
        )

        st.plotly_chart(fig, use_container_width=True)
        
        # E. 快速操作建議 (根據 EMA)
        if price > latest['EMA_20']:
            st.success(f"🔥 **動能強勁：** {selected_ticker} 目前站穩 EMA 20 之上，屬於強勢攻擊型態。")
        elif price < latest['EMA_200']:
            st.error(f"⚠️ **空頭警報：** {selected_ticker} 跌破 EMA 200 生命線，建議保守觀望。")
        else:
            st.info(f"⚖️ **盤整震盪：** {selected_ticker} 介於均線之間，等待方向確認。")

    else:
        st.error("無法讀取數據，請確認代碼。")
