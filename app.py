import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import os

# --- 1. 檔案系統設定 (CSV Persistence) ---
CSV_FILE = 'my_portfolio.csv'

def load_portfolio():
    if os.path.exists(CSV_FILE):
        return pd.read_csv(CSV_FILE)
    else:
        # 預設資料 (如果檔案不存在)
        default_data = {
            'Ticker': ['NVDA', 'TSLA', 'AAPL', 'AMD'],
            'Cost': [450.0, 220.5, 0.0, 110.0],
            'Type': ['Holding', 'Holding', 'Watchlist', 'Holding'], # Holding / Watchlist
            'Note': ['AI 霸主', '馬斯克', '觀察中', '二哥']
        }
        return pd.DataFrame(default_data)

def save_portfolio(df):
    df.to_csv(CSV_FILE, index=False)

# --- 2. 頁面設定 ---
st.set_page_config(page_title="戰術狙擊鏡 v3.0", layout="wide")
st.title("🎯 戰術狙擊鏡 (Tactical Sniper)")

# --- 3. 數據核心 ---
@st.cache_data(ttl=300)
def get_stock_data(ticker, period="1y"):
    try:
        df = yf.download(ticker, period=period, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.reset_index()
        # 技術指標
        df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
        df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
        df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
        return df
    except:
        return None

# --- 4. 主介面邏輯 (Tabs UX) ---
tab1, tab2 = st.tabs(["📊 戰術看板 (Dashboard)", "📝 庫存管理 (Editor)"])

# ==========================================
# TAB 2: 庫存管理 (Excel 風格編輯器)
# ==========================================
with tab2:
    st.markdown("### ⚡️ 快速管理清單")
    st.info("💡 **操作指南：** 直接點擊表格內容修改。點擊最後一列的 `+` 新增股票。選取行並按 Delete 刪除。修改完畢系統會自動儲存。")
    
    # 讀取現有清單
    current_df = load_portfolio()
    
    # 顯示可編輯的 Dataframe (這是 Streamlit 最潮的元件)
    edited_df = st.data_editor(
        current_df,
        num_rows="dynamic", # 允許新增/刪除行
        use_container_width=True,
        column_config={
            "Ticker": st.column_config.TextColumn("股票代碼", help="輸入美股代碼 (例如 NVDA)", validate="^[A-Za-z0-9.-]+$", required=True),
            "Cost": st.column_config.NumberColumn("成本價 (USD)", help="若是觀察名單可填 0", format="$%.2f"),
            "Type": st.column_config.SelectboxColumn("狀態", options=["Holding", "Watchlist"], required=True),
            "Note": st.column_config.TextColumn("筆記", help="寫點什麼...")
        },
        key="editor"
    )

    # 自動存檔邏輯
    # 當 edited_df 與 current_df 不同時，寫入 CSV
    if not edited_df.equals(current_df):
        save_portfolio(edited_df)
        st.toast("✅ 投資組合已更新並儲存！", icon="💾")
        st.rerun() # 重新整理以更新 Dashboard

# ==========================================
# TAB 1: 戰術看板 (Dashboard)
# ==========================================
with tab1:
    # 重新讀取最新的資料 (確保 Tab 2 修改後這裡同步)
    portfolio_df = load_portfolio()
    
    # 側邊欄控制
    with st.sidebar:
        st.header("🔭 戰術導航")
        
        # 過濾器 UX
        filter_type = st.radio("顯示模式", ["全部", "💰 持倉 (Holding)", "👀 關注 (Watchlist)"])
        
        if filter_type == "💰 持倉 (Holding)":
            filtered_df = portfolio_df[portfolio_df['Type'] == 'Holding']
        elif filter_type == "👀 關注 (Watchlist)":
            filtered_df = portfolio_df[portfolio_df['Type'] == 'Watchlist']
        else:
            filtered_df = portfolio_df
            
        # 選擇股票 UX
        # 這裡我們做一個漂亮的標籤： "NVDA ($450) - AI霸主"
        if not filtered_df.empty:
            select_options = filtered_df.apply(
                lambda x: f"{x['Ticker']} {'($' + str(x['Cost']) + ')' if x['Cost'] > 0 else ''}", axis=1
            ).tolist()
            
            selected_label = st.selectbox("選擇標的", select_options)
            
            # 解析回 Ticker
            selected_ticker = selected_label.split(' ')[0]
            
            # 抓取對應的 Cost 和 Note
            row = portfolio_df[portfolio_df['Ticker'] == selected_ticker].iloc[0]
            cost_basis = row['Cost'] if row['Cost'] > 0 else None
            note = row['Note']
            
            st.divider()
            st.caption(f"📝 筆記: {note}")
            
            # 圖表參數
            time_range = st.select_slider("K線範圍", options=["3mo", "6mo", "1y", "3y", "5y"], value="1y")
            show_ema = st.multiselect("均線", ["EMA 20", "EMA 50", "EMA 200"], default=["EMA 20", "EMA 50"])

    # 主畫面圖表
    if not portfolio_df.empty and 'selected_ticker' in locals():
        df = get_stock_data(selected_ticker, time_range)
        
        if df is not None:
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            price = latest['Close']
            change = price - prev['Close']
            pct_change = (change / prev['Close']) * 100
            
            # 上方 Metric
            c1, c2, c3, c4 = st.columns(4)
            c1.metric(f"{selected_ticker}", f"{price:.2f}", f"{change:.2f} ({pct_change:.2f}%)")
            
            if cost_basis:
                pl = price - cost_basis
                pl_pct = (pl / cost_basis) * 100
                c2.metric("損益", f"{pl_pct:+.2f}%", f"{pl:+.2f}", delta_color="normal" if pl > 0 else "inverse")
            else:
                c2.metric("狀態", "觀察中 👀")
                
            c3.metric("EMA 20", f"{latest['EMA_20']:.2f}")
            c4.metric("EMA 50", f"{latest['EMA_50']:.2f}")
            
            # 繪圖
            fig = go.Figure()
            fig.add_trace(go.Candlestick(x=df['Date'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"))
            
            # 成本線
            if cost_basis:
                fig.add_hline(y=cost_basis, line_dash="dash", line_color="yellow", annotation_text="COST")
                
            # 均線
            colors = {'EMA 20': '#00FF00', 'EMA 50': '#FFA500', 'EMA 200': '#FF0000'}
            for ema in show_ema:
                col = ema.replace(" ", "_")
                fig.add_trace(go.Scatter(x=df['Date'], y=df[col], name=ema, line=dict(color=colors[ema], width=1.5)))

            fig.update_layout(height=650, hovermode="x unified", xaxis_rangeslider_visible=False, template="plotly_dark", title=f"{selected_ticker} 技術分析")
            st.plotly_chart(fig, use_container_width=True)
            
        else:
            st.error("無法讀取數據，請檢查代碼是否正確。")
    else:
        st.info("👈 請先到「庫存管理」分頁新增股票！")
