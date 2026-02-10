import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
import json

# --- 1. Google Apps Script 設定 ---
# 請把你剛剛複製的 "Web App URL" 貼在 Streamlit Secrets 裡，或者直接貼這裡測試
# 建議放在 .streamlit/secrets.toml -> [app_script] url = "你的網址"
# 為了方便你直接跑，我們先用變數 (請填入你的網址)
GAS_URL = "https://script.google.com/macros/s/AKfycbzrtQuZBlNAdHDEhOwN10wpmqR1YH-RBJIAYoRVisbz55x2kF4zQ9JOcYuD8R7P-W1BxQ/exec" 

# 如果你有設定 secrets，就優先讀取 secrets
if "app_script" in st.secrets:
    GAS_URL = st.secrets["app_script"]["url"]

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
        st.error(f"❌ 無法連線至 Google Sheet: {e}")
        return pd.DataFrame(columns=['Ticker', 'Cost', 'Type', 'Note'])

def save_portfolio(df):
    try:
        # 準備要上傳的資料：標題 + 內容
        # 轉換成 List of Lists 格式
        header = df.columns.tolist()
        values = df.values.tolist()
        payload = {'data': [header] + values}
        
        # 發送 POST 請求寫入資料
        response = requests.post(GAS_URL, json=payload)
        
        if response.status_code != 200:
             st.error("寫入失敗，請檢查 Apps Script 部署設定。")
             
    except Exception as e:
        st.error(f"❌ 無法寫入 Google Sheet: {e}")

# --- 2. 頁面設定 ---
st.set_page_config(page_title="戰術狙擊鏡 v5.0 (GAS)", layout="wide")
st.title("🦅 戰術狙擊鏡 (No-GCP Backend)")

if GAS_URL == "你的_Google_Apps_Script_網址_貼在這裡":
    st.warning("⚠️ 請先在程式碼中填入你的 Apps Script 網址，或設定 Secrets！")
    st.stop()

# --- 3. 數據核心 (不變) ---
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

with tab2:
    st.markdown("### ☁️ 輕量級雲端同步")
    st.caption("Backend: Google Apps Script (No GCP Required)")
    
    current_df = load_portfolio()
    
    edited_df = st.data_editor(
        current_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Ticker": st.column_config.TextColumn("代碼", required=True),
            "Cost": st.column_config.NumberColumn("成本", format="$%.2f"),
            "Type": st.column_config.SelectboxColumn("狀態", options=["Holding", "Watchlist"], required=True),
            "Note": st.column_config.TextColumn("筆記")
        },
        key="editor"
    )

    if not edited_df.equals(current_df):
        with st.spinner("正在呼叫 GAS API 同步中..."):
            save_portfolio(edited_df)
        st.success("✅ 同步完成！")
        st.rerun()

with tab1:
    portfolio_df = load_portfolio()
    
    with st.sidebar:
        st.header("🔭 戰術導航")
        filter_type = st.radio("模式", ["全部", "💰 持倉", "👀 關注"])
        
        if filter_type == "💰 持倉": filtered_df = portfolio_df[portfolio_df['Type'] == 'Holding']
        elif filter_type == "👀 關注": filtered_df = portfolio_df[portfolio_df['Type'] == 'Watchlist']
        else: filtered_df = portfolio_df
            
        if not filtered_df.empty:
            select_options = filtered_df.apply(lambda x: f"{x['Ticker']} {'($' + str(x['Cost']) + ')' if x['Cost'] > 0 else ''}", axis=1).tolist()
            selected_label = st.selectbox("選擇標的", select_options)
            selected_ticker = selected_label.split(' ')[0]
            
            row = portfolio_df[portfolio_df['Ticker'] == selected_ticker].iloc[0]
            cost_basis = row['Cost'] if row['Cost'] > 0 else None
            
            st.divider()
            time_range = st.select_slider("範圍", options=["3mo", "6mo", "1y", "3y"], value="6mo")

    if not portfolio_df.empty and 'selected_ticker' in locals():
        df = get_stock_data(selected_ticker, time_range)
        if df is not None:
            latest = df.iloc[-1]
            price = latest['Close']
            
            c1, c2, c3 = st.columns(3)
            c1.metric(selected_ticker, f"{price:.2f}")
            if cost_basis:
                pl_pct = ((price - cost_basis) / cost_basis) * 100
                c2.metric("損益", f"{pl_pct:+.2f}%", delta_color="normal" if pl_pct > 0 else "inverse")
            
            fig = go.Figure()
            fig.add_trace(go.Candlestick(x=df['Date'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"))
            if cost_basis: fig.add_hline(y=cost_basis, line_dash="dash", line_color="yellow")
            
            fig.add_trace(go.Scatter(x=df['Date'], y=df['EMA_20'], name="EMA 20", line=dict(color='green', width=1)))
            fig.add_trace(go.Scatter(x=df['Date'], y=df['EMA_50'], name="EMA 50", line=dict(color='orange', width=1)))
            
            fig.update_layout(height=600, hovermode="x unified", template="plotly_dark", xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
import json

# --- 1. Google Apps Script 設定 ---
# 請把你剛剛複製的 "Web App URL" 貼在 Streamlit Secrets 裡，或者直接貼這裡測試
# 建議放在 .streamlit/secrets.toml -> [app_script] url = "你的網址"
# 為了方便你直接跑，我們先用變數 (請填入你的網址)
GAS_URL = "你的_Google_Apps_Script_網址_貼在這裡" 

# 如果你有設定 secrets，就優先讀取 secrets
if "app_script" in st.secrets:
    GAS_URL = st.secrets["app_script"]["url"]

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
        st.error(f"❌ 無法連線至 Google Sheet: {e}")
        return pd.DataFrame(columns=['Ticker', 'Cost', 'Type', 'Note'])

def save_portfolio(df):
    try:
        # 準備要上傳的資料：標題 + 內容
        # 轉換成 List of Lists 格式
        header = df.columns.tolist()
        values = df.values.tolist()
        payload = {'data': [header] + values}
        
        # 發送 POST 請求寫入資料
        response = requests.post(GAS_URL, json=payload)
        
        if response.status_code != 200:
             st.error("寫入失敗，請檢查 Apps Script 部署設定。")
             
    except Exception as e:
        st.error(f"❌ 無法寫入 Google Sheet: {e}")

# --- 2. 頁面設定 ---
st.set_page_config(page_title="戰術狙擊鏡 v5.0 (GAS)", layout="wide")
st.title("🦅 戰術狙擊鏡 (No-GCP Backend)")

if GAS_URL == "你的_Google_Apps_Script_網址_貼在這裡":
    st.warning("⚠️ 請先在程式碼中填入你的 Apps Script 網址，或設定 Secrets！")
    st.stop()

# --- 3. 數據核心 (不變) ---
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

with tab2:
    st.markdown("### ☁️ 輕量級雲端同步")
    st.caption("Backend: Google Apps Script (No GCP Required)")
    
    current_df = load_portfolio()
    
    edited_df = st.data_editor(
        current_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Ticker": st.column_config.TextColumn("代碼", required=True),
            "Cost": st.column_config.NumberColumn("成本", format="$%.2f"),
            "Type": st.column_config.SelectboxColumn("狀態", options=["Holding", "Watchlist"], required=True),
            "Note": st.column_config.TextColumn("筆記")
        },
        key="editor"
    )

    if not edited_df.equals(current_df):
        with st.spinner("正在呼叫 GAS API 同步中..."):
            save_portfolio(edited_df)
        st.success("✅ 同步完成！")
        st.rerun()

with tab1:
    portfolio_df = load_portfolio()
    
    with st.sidebar:
        st.header("🔭 戰術導航")
        filter_type = st.radio("模式", ["全部", "💰 持倉", "👀 關注"])
        
        if filter_type == "💰 持倉": filtered_df = portfolio_df[portfolio_df['Type'] == 'Holding']
        elif filter_type == "👀 關注": filtered_df = portfolio_df[portfolio_df['Type'] == 'Watchlist']
        else: filtered_df = portfolio_df
            
        if not filtered_df.empty:
            select_options = filtered_df.apply(lambda x: f"{x['Ticker']} {'($' + str(x['Cost']) + ')' if x['Cost'] > 0 else ''}", axis=1).tolist()
            selected_label = st.selectbox("選擇標的", select_options)
            selected_ticker = selected_label.split(' ')[0]
            
            row = portfolio_df[portfolio_df['Ticker'] == selected_ticker].iloc[0]
            cost_basis = row['Cost'] if row['Cost'] > 0 else None
            
            st.divider()
            time_range = st.select_slider("範圍", options=["3mo", "6mo", "1y", "3y"], value="6mo")

    if not portfolio_df.empty and 'selected_ticker' in locals():
        df = get_stock_data(selected_ticker, time_range)
        if df is not None:
            latest = df.iloc[-1]
            price = latest['Close']
            
            c1, c2, c3 = st.columns(3)
            c1.metric(selected_ticker, f"{price:.2f}")
            if cost_basis:
                pl_pct = ((price - cost_basis) / cost_basis) * 100
                c2.metric("損益", f"{pl_pct:+.2f}%", delta_color="normal" if pl_pct > 0 else "inverse")
            
            fig = go.Figure()
            fig.add_trace(go.Candlestick(x=df['Date'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"))
            if cost_basis: fig.add_hline(y=cost_basis, line_dash="dash", line_color="yellow")
            
            fig.add_trace(go.Scatter(x=df['Date'], y=df['EMA_20'], name="EMA 20", line=dict(color='green', width=1)))
            fig.add_trace(go.Scatter(x=df['Date'], y=df['EMA_50'], name="EMA 50", line=dict(color='orange', width=1)))
            
            fig.update_layout(height=600, hovermode="x unified", template="plotly_dark", xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
