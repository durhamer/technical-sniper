import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests

# --- 1. Google Apps Script 設定 ---
# 這是你專屬的 API 網址 (已經幫你填好了)
GAS_URL = "https://script.google.com/macros/s/AKfycbzrtQuZBlNAdHDEhOwN10wpmqR1YH-RBJIAYoRVisbz55x2kF4zQ9JOcYuD8R7P-W1BxQ/exec"

def load_portfolio():
    try:
        # 發送 GET 請求讀取資料
        response = requests.get(GAS_URL)
        data = response.json()
        df = pd.DataFrame(data)
        
        if df.empty:
             return pd.DataFrame(columns=['Ticker', 'Cost', 'Type', 'Note'])
             
        # 強制轉型
        df['Cost'] = pd.to_numeric(df['Cost'], errors='coerce').fillna(0.0)
        return df
    except Exception as e:
        # 如果發生錯誤，顯示空表格
        return pd.DataFrame(columns=['Ticker', 'Cost', 'Type', 'Note'])

def save_portfolio(df):
    try:
        # 準備要上傳的資料：標題 + 內容
        header = df.columns.tolist()
        values = df.values.tolist()
        payload = {'data': [header] + values}
        
        # 發送 POST 請求寫入資料
        requests.post(GAS_URL, json=payload)
             
    except Exception as e:
        st.error(f"❌ 無法寫入 Google Sheet: {e}")

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
        # 技術指標
        df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
        df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
        df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
        return df
    except:
        return None

# --- 4. 主介面邏輯 ---
tab1, tab2 = st.tabs(["📊 戰術看板", "📝 庫存管理"])

# ==========================================
# TAB 2: 庫存管理 (編輯器)
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
# TAB 1: 戰術看板 (圖表)
# ==========================================
with tab1:
    portfolio_df = load_portfolio()
    
    with st.sidebar:
        st.header("🔭 戰術導航")
        
        # 篩選器
        filter_type = st.radio("模式", ["全部", "💰 持倉", "👀 關注"])
        
        if filter_type == "💰 持倉":
            filtered_df = portfolio_df[portfolio_df['Type'] == 'Holding']
        elif filter_type == "👀 關注":
            filtered_df = portfolio_df[portfolio_df['Type'] == 'Watchlist']
        else:
            filtered_df = portfolio_df
            
        # 選擇股票
        if not filtered_df.empty:
            select_options = filtered_df.apply(
                lambda x: f"{x['Ticker']} {'($' + str(x['Cost']) + ')' if x['Cost'] > 0 else ''}", axis=1
            ).tolist()
            
            selected_label = st.selectbox("選擇標的", select_options)
            selected_ticker = selected_label.split(' ')[0]
            
            # 抓取對應資訊
            row = portfolio_df[portfolio_df['Ticker'] == selected_ticker].iloc[0]
            cost_basis = row['Cost'] if row['Cost'] > 0 else None
            note = row.get('Note', '')
            
            st.divider()
            if note:
                st.caption(f"📝 筆記: {note}")
