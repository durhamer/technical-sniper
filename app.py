import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests

# --- 1. Google Apps Script 設定 ---
GAS_URL = "https://script.google.com/macros/s/AKfycbxbRhj557u8nwTMR6uyYQsUAaAVldnlOHHrBJHKMrai9zuVURxqw7GcoFJY-S1Ct3Tsxw/exec"

def load_portfolio():
    try:
        response = requests.get(GAS_URL)
        data = response.json()
        df = pd.DataFrame(data)
        
        if df.empty:
             return pd.DataFrame(columns=['Ticker', 'Cost', 'Type', 'Note'])
             
        df['Cost'] = pd.to_numeric(df['Cost'], errors='coerce').fillna(0.0)
        return df
    except Exception as e:
        return pd.DataFrame(columns=['Ticker', 'Cost', 'Type', 'Note'])

def save_portfolio(df):
    try:
        header = df.columns.tolist()
        values = df.values.tolist()
        values = [[str(x) if pd.isna(x) else x for x in row] for row in values]
        
        payload = {'data': [header] + values}
        
        response = requests.post(GAS_URL, json=payload)
        
        try:
            result = response.json()
        except:
            st.error(f"❌ 嚴重錯誤：Google 回傳了無法解析的內容。")
            return

        if result.get('status') == 'success':
            st.toast("✅ 雲端寫入成功！", icon="☁️")
        else:
            st.error(f"❌ 寫入失敗 (GAS Error)：{result.get('message')}")
            st.stop()
             
    except Exception as e:
        st.error(f"❌ 連線錯誤: {e}")
        st.stop()

# --- 2. 頁面設定 ---
st.set_page_config(page_title="戰術狙擊鏡 v5.0", layout="wide")
st.title("🦅 戰術狙擊鏡 (Cloud Database)")

# --- 3. 數據核心 ---
@st.cache_data(ttl=300)
def get_stock_data(ticker, period="1y"):
    try:
        df = yf.download(ticker, period=period, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.reset_index()
        df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
        df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
        df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
        return df
    except:
        return None

# --- 4. 主介面邏輯 ---
tab1, tab2 = st.tabs(["📊 戰術看板", "📝 庫存管理"])

# ==========================================
# TAB 2: 庫存管理
# ==========================================
with tab2:
    st.markdown("### ☁️ 雲端庫存管理")
    st.caption("Backend: Google Sheets (via Apps Script)")
    st.info("💡 **操作指南：** 修改表格內容後（例如新增股票、更改成本），系統會自動同步回 Google Drive。")
    
    current_df = load_portfolio()
    
    edited_df = st.data_editor(
        current_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Ticker": st.column_config.TextColumn("代碼", required=True, validate="^[A-Za-z0-9.-]+$"),
            "Cost": st.column_config.NumberColumn("成本", format="$%.2f"),
            "Type": st.column_config.SelectboxColumn("狀態", options=["Holding", "Watchlist"], required=True),
            "Note": st.column_config.TextColumn("筆記")
        },
        key="editor"
    )

    if not edited_df.equals(current_df):
        with st.spinner("正在同步至 Google Drive..."):
            save_portfolio(edited_df)
        st.success("✅ 同步完成！")
        st.rerun()

# ==========================================
# TAB 1: 戰術看板 (這裡就是你之前缺失的引擎！)
# ==========================================
with tab1:
    portfolio_df = load_portfolio()
    
    # 預設變數，防止未選擇時報錯
    selected_ticker = None
    time_range = "1y" 

    with st.sidebar:
        st.header("🔭 戰術導航")
        
        filter_type = st.radio("模式", ["全部", "💰 持倉", "👀 關注"])
        
        if filter_type == "💰 持倉":
            filtered_df = portfolio_df[portfolio_df['Type'] == 'Holding']
        elif filter_type == "👀 關注":
            filtered_df = portfolio_df[portfolio_df['Type'] == 'Watchlist']
        else:
            filtered_df = portfolio_df
            
        if not filtered_df.empty:
            select_options = filtered_df.apply(
                lambda x: f"{x['Ticker']} {'($' + str(x['Cost']) + ')' if x['Cost'] > 0 else ''}", axis=1
            ).tolist()
            
            selected_label = st.selectbox("選擇標的", select_options)
            selected_ticker = selected_label.split(' ')[0]
            
            row = portfolio_df[portfolio_df['Ticker'] == selected_ticker].iloc[0]
            cost_basis = row['Cost'] if row['Cost'] > 0 else None
            note = row.get('Note', '')
            
            st.divider()
            if note:
                st.caption(f"📝 筆記: {note}")
            
            # 這是你之前漏掉的控制項
            time_range = st.select_slider("K線範圍", options=["3mo", "6mo", "1y", "3y", "5y"], value="1y")

    # 這是你之前完全漏掉的繪圖邏輯
    if selected_ticker:
        df = get_stock_data(selected_ticker, time_range)
        
        if df is not None:
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            price = latest['Close']
            change = price - prev['Close']
            pct_change = (change / prev['Close']) * 100
            
            # 上方資訊卡
            c1, c2, c3, c4 = st.columns(4)
            c1.metric(selected_ticker, f"{price:.2f}", f"{change:.2f} ({pct_change:.2f}%)")
            
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
            
            if cost_basis:
                fig.add_hline(y=cost_basis, line_dash="dash", line_color="yellow", annotation_text="COST")
                
            fig.add_trace(go.Scatter(x=df['Date'], y=df['EMA_20'], name="EMA 20", line=dict(color='#00FF00', width=1.5)))
            fig.add_trace(go.Scatter(x=df['Date'], y=df['EMA_50'], name="EMA 50", line=dict(color='#FFA500', width=1.5)))
            fig.add_trace(go.Scatter(x=df['Date'], y=df['EMA_200'], name="EMA 200", line=dict(color='#FF0000', width=1.5)))

            fig.update_layout(height=650, hovermode="x unified", template="plotly_dark", xaxis_rangeslider_visible=False, title=f"{selected_ticker} 技術分析")
            st.plotly_chart(fig, use_container_width=True)
            
        else:
            st.error("無法讀取數據，請檢查代碼。")
    else:
        st.info("👈 資料庫是空的，請先到「庫存管理」分頁新增股票！")
