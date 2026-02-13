import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from datetime import datetime, timedelta

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
st.set_page_config(page_title="戰術狙擊鏡 v7.1 (Stable)", layout="wide")
st.title("🦅 戰術狙擊鏡 (Pro Edition)")

# --- 3. 數據核心 ---
@st.cache_data(ttl=300)
def get_stock_data(ticker, period="1y"):
    mapping = {
        "SOX": "^SOX", "NDX": "^NDX", "DJI": "^DJI", "GSPC": "^GSPC", 
        "VIX": "^VIX", "BTC": "BTC-USD", "ETH": "ETH-USD"
    }
    target_ticker = mapping.get(ticker.upper(), ticker)

    try:
        df = yf.download(target_ticker, period=period, progress=False)
        if df.empty: return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.reset_index()
        
        # EMA
        df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
        df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
        df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
        
        # MACD
        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2
        df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['Hist'] = df['MACD'] - df['Signal']
        
        return df
    except Exception as e:
        return None

@st.cache_data(ttl=86400)
def get_shares_data(ticker):
    """
    獲取流通股數歷史數據 (v7.1 Stable: 改抓資產負債表)
    """
    if "^" in ticker or "USD" in ticker: return None, None

    try:
        tk = yf.Ticker(ticker)
        
        # 嘗試方法 1: 從資產負債表抓 (Balance Sheet) - 這是最標準的季報數據
        try:
            bs = tk.balance_sheet
            # 尋找類似 'Share Issued' 或 'Common Stock' 的欄位
            # yfinance 的欄位名稱有時候會變，這裡做個模糊搜尋
            share_row = None
            possible_names = ['Share Issued', 'Ordinary Shares Number', 'Common Stock', 'Capital Stock']
            
            for name in possible_names:
                if name in bs.index:
                    share_row = bs.loc[name]
                    break
            
            if share_row is not None:
                shares_df = pd.DataFrame(share_row).sort_index()
                shares_df.columns = ['Shares']
                shares_df.index = pd.to_datetime(shares_df.index)
                
                # 計算 YoY (拿最近一期跟四期前比)
                if len(shares_df) >= 2:
                    latest = shares_df['Shares'].iloc[-1]
                    prev = shares_df['Shares'].iloc[0] # 最舊的數據
                    yoy_change = ((latest - prev) / prev) * 100
                    return shares_df, yoy_change
        except:
            pass # 如果資產負債表失敗，就往下走

        # 嘗試方法 2: 只抓最新數據 (Info)
        info = tk.info
        latest_shares = info.get('sharesOutstanding')
        
        if latest_shares:
            # 造一個假的 DataFrame 只有一點，為了顯示 Current 數值
            return None, 0.0 # 沒有歷史數據，回傳 0.0 表示無法計算趨勢
            
        return None, None

    except Exception as e:
        print(f"❌ Error getting shares for {ticker}: {e}")
        return None, None

# --- 4. 主介面邏輯 ---
tab1, tab2 = st.tabs(["📊 戰術看板", "📝 庫存管理"])

# ==========================================
# TAB 2: 庫存管理
# ==========================================
with tab2:
    st.markdown("### ☁️ 雲端庫存管理")
    st.caption("Backend: Google Sheets (via Apps Script)")
    
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
# TAB 1: 戰術看板
# ==========================================
with tab1:
    portfolio_df = load_portfolio()
    
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
            
            time_range = st.select_slider("K線範圍", options=["3mo", "6mo", "1y", "3y", "5y"], value="1y")
            
            st.divider()
            st.markdown("### 🕵️‍♂️ 外部情報")
            st.link_button("📊 查看 DIX / GEX (暗池)", "https://squeezemetrics.com/monitor/dix", help="前往 SqueezeMetrics 查看暗池指標")

    if selected_ticker:
        # 1. 取得價格數據
        df = get_stock_data(selected_ticker, time_range)
        
        # 2. 取得回購數據
        shares_df, shares_yoy = get_shares_data(selected_ticker)
        
        if df is not None and not df.empty:
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            price = latest['Close']
            change = price - prev['Close']
            pct_change = (change / prev['Close']) * 100
            
            # --- 頂部指標區 ---
            c1, c2, c3, c4 = st.columns(4)
            c1.metric(selected_ticker, f"{price:.2f}", f"{change:.2f} ({pct_change:.2f}%)")
            
            if cost_basis:
                pl = price - cost_basis
                pl_pct = (pl / cost_basis) * 100
                c2.metric("損益", f"{pl_pct:+.2f}%", f"{pl:+.2f}", delta_color="normal" if pl > 0 else "inverse")
            else:
                c2.metric("狀態", "觀察中 👀")
            
            # 回購指標顯示
            if shares_yoy is not None and shares_yoy != 0:
                delta_color = "normal" if shares_yoy < 0 else "inverse" 
                trend_text = "縮減 (回購)" if shares_yoy < 0 else "增加 (稀釋)"
                c3.metric("流通股數 Trend", f"{shares_yoy:.2f}%", trend_text, delta_color=delta_color)
            elif shares_yoy == 0:
                 c3.metric("流通股數", "Data OK", "趨勢持平/無歷史")
            else:
                c3.metric("流通股數", "N/A", "無法取得")

            c4.metric("EMA 20", f"{latest['EMA_20']:.2f}")
            
            # --- 主圖表區 ---
            fig = make_subplots(
                rows=2, cols=1, 
                shared_xaxes=True, 
                vertical_spacing=0.03, 
                row_heights=[0.7, 0.3],
                subplot_titles=(f"{selected_ticker} Price Action", "MACD Momentum")
            )

            # Row 1: Price
            fig.add_trace(go.Candlestick(x=df['Date'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"), row=1, col=1)
            if cost_basis:
                fig.add_hline(y=cost_basis, line_dash="dash", line_color="yellow", annotation_text="COST", row=1, col=1)
            fig.add_trace(go.Scatter(x=df['Date'], y=df['EMA_20'], name="EMA 20", line=dict(color='#00FF00', width=1.5)), row=1, col=1)
            fig.add_trace(go.Scatter(x=df['Date'], y=df['EMA_50'], name="EMA 50", line=dict(color='#FFA500', width=1.5)), row=1, col=1)
            fig.add_trace(go.Scatter(x=df['Date'], y=df['EMA_200'], name="EMA 200", line=dict(color='#FF0000', width=1.5)), row=1, col=1)

            # Row 2: MACD
            colors = ['#00FF00' if v >= 0 else '#FF0000' for v in df['Hist']]
            fig.add_trace(go.Bar(x=df['Date'], y=df['Hist'], name="Histogram", marker_color=colors), row=2, col=1)
            fig.add_trace(go.Scatter(x=df['Date'], y=df['MACD'], name="MACD", line=dict(color='#00FFFF', width=1.5)), row=2, col=1)
            fig.add_trace(go.Scatter(x=df['Date'], y=df['Signal'], name="Signal", line=dict(color='#FF00FF', width=1.5)), row=2, col=1)

            fig.update_layout(
                height=700,
                hovermode="x unified",
                template="plotly_dark",
                xaxis_rangeslider_visible=False,
                legend=dict(x=0, y=1, xanchor="left", yanchor="top", bgcolor='rgba(0,0,0,0.3)'),
                yaxis1=dict(side="right", showline=True),
                yaxis2=dict(side="right", showline=True)
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # --- 隱藏式：回購深入分析 (The Sniper View) ---
            if shares_df is not None:
                with st.expander("🛡️ 護城河偵測：回購與股權分析 (Buyback Analysis)", expanded=False):
                    st.caption("數據來源：年度/季度 資產負債表 (Share Issued)")
                    
                    # 建立雙軸圖表
                    fig_buyback = make_subplots(specs=[[{"secondary_y": True}]])
                    
                    # 軸1：股價
                    fig_buyback.add_trace(
                        go.Scatter(x=df['Date'], y=df['Close'], name="股價 (Price)", line=dict(color='#00FFFF', width=2)),
                        secondary_y=False
                    )
                    
                    # 軸2：流通股數 (使用 Bar chart 因為財報數據是離散的)
                    fig_buyback.add_trace(
                        go.Bar(
                            x=shares_df.index, 
                            y=shares_df['Shares'], 
                            name="流通股數 (Shares Issued)", 
                            marker_color='#FFA500',
                            opacity=0.6
                        ),
                        secondary_y=True
                    )
                    
                    fig_buyback.update_layout(
                        title=f"{selected_ticker} - 股價 vs 股本變化",
                        template="plotly_dark",
                        height=400,
                        hovermode="x unified",
                        legend=dict(orientation="h", y=1.1)
                    )
                    
                    fig_buyback.update_yaxes(title_text="股價 Price", secondary_y=False)
                    fig_buyback.update_yaxes(title_text="流通股數 Shares", secondary_y=True, showgrid=False)

                    st.plotly_chart(fig_buyback, use_container_width=True)
            
        else:
            st.warning(f"⚠️ 找不到 **{selected_ticker}** 的數據。")
    else:
        st.info("👈 請先選擇股票！")
