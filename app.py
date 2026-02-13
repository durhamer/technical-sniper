import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from datetime import datetime, date

# --- 1. Google Apps Script 設定 ---
GAS_URL = "https://script.google.com/macros/s/AKfycbxbRhj557u8nwTMR6uyYQsUAaAVldnlOHHrBJHKMrai9zuVURxqw7GcoFJY-S1Ct3Tsxw/exec"

def load_portfolio():
    try:
        response = requests.get(GAS_URL)
        data = response.json()
        df = pd.DataFrame(data)
        if df.empty: return pd.DataFrame(columns=['Ticker', 'Cost', 'Type', 'Note'])
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
        
        try: result = response.json()
        except:
            st.error("❌ 嚴重錯誤：Google 回傳了無法解析的內容。")
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
st.set_page_config(page_title="戰術狙擊鏡 v7.8 (Macro Radar)", layout="wide")
st.title("🦅 戰術狙擊鏡 (Pro Edition)")

# --- 3. 數據核心 ---
@st.cache_data(ttl=300)
def get_stock_data(ticker, period="2y"):
    mapping = {"SOX": "^SOX", "NDX": "^NDX", "DJI": "^DJI", "GSPC": "^GSPC", "VIX": "^VIX", "BTC": "BTC-USD", "ETH": "ETH-USD"}
    target_ticker = mapping.get(ticker.upper(), ticker)
    try:
        df = yf.download(target_ticker, period=period, progress=False)
        if df.empty: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
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
    except: return None

@st.cache_data(ttl=86400)
def get_shares_data(ticker):
    if "^" in ticker or "USD" in ticker: return None, None
    try:
        tk = yf.Ticker(ticker)
        try:
            bs = tk.quarterly_balance_sheet
            if bs.empty: bs = tk.balance_sheet 
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
        except: pass 
        info = tk.info
        if info.get('sharesOutstanding'): return None, 0.0 
        return None, None
    except: return None, None

@st.cache_data(ttl=86400)
def get_earnings_date(ticker):
    if "^" in ticker or "USD" in ticker: return None
    try:
        tk = yf.Ticker(ticker)
        cal = tk.calendar
        if cal is not None and 'Earnings Date' in cal:
            dates = cal['Earnings Date']
            if isinstance(dates, list) and len(dates) > 0: return dates[0]
    except: pass
    return None

@st.cache_data(ttl=86400)
def get_smart_money_data(ticker):
    if "^" in ticker or "USD" in ticker: return None, None
    try:
        info = yf.Ticker(ticker).info
        i = info.get('heldPercentInstitutions')
        s = info.get('shortPercentOfFloat')
        return (i * 100) if i is not None else None, (s * 100) if s is not None else None
    except: return None, None

@st.cache_data(ttl=86400)
def get_institutional_holders(ticker):
    if "^" in ticker or "USD" in ticker: return None
    try:
        df = yf.Ticker(ticker).institutional_holders
        if df is not None and not df.empty: return df
    except: pass
    return None

# --- 4. 主介面邏輯 ---
tab1, tab2 = st.tabs(["📊 戰術看板", "📝 庫存管理"])

with tab2:
    st.markdown("### ☁️ 雲端庫存管理")
    current_df = load_portfolio()
    edited_df = st.data_editor(
        current_df, num_rows="dynamic", use_container_width=True,
        column_config={
            "Ticker": st.column_config.TextColumn("代碼", required=True),
            "Cost": st.column_config.NumberColumn("成本", format="$%.2f"),
            "Type": st.column_config.SelectboxColumn("狀態", options=["Holding", "Watchlist"], required=True),
            "Note": st.column_config.TextColumn("筆記")
        }, key="editor"
    )
    if not edited_df.equals(current_df):
        with st.spinner("同步中..."): save_portfolio(edited_df)
        st.success("✅ 同步完成！")
        st.rerun()

with tab1:
    portfolio_df = load_portfolio()
    selected_ticker = None
    time_range = "2y"

    with st.sidebar:
        st.header("🔭 戰術導航")
        filter_type = st.radio("模式", ["全部", "💰 持倉", "👀 關注"])
        
        filtered_df = portfolio_df
        if filter_type == "💰 持倉": filtered_df = portfolio_df[portfolio_df['Type'] == 'Holding']
        elif filter_type == "👀 關注": filtered_df = portfolio_df[portfolio_df['Type'] == 'Watchlist']
            
        select_options = ["📡 總覽雷達 (Macro Radar)"]
        if not filtered_df.empty:
            select_options += filtered_df.apply(lambda x: f"{x['Ticker']} {'($' + str(x['Cost']) + ')' if x['Cost'] > 0 else ''}", axis=1).tolist()
            
        selected_label = st.selectbox("選擇標的", select_options)
        
        if selected_label == "📡 總覽雷達 (Macro Radar)":
            selected_ticker = None
        else:
            selected_ticker = selected_label.split(' ')[0]
            row = portfolio_df[portfolio_df['Ticker'] == selected_ticker].iloc[0]
            cost_basis = row['Cost'] if row['Cost'] > 0 else None
            note = row.get('Note', '')
            st.divider()
            if note: st.caption(f"📝 筆記: {note}")
            time_range = st.select_slider("K線範圍", options=["6mo", "1y", "2y", "5y"], value="2y")
            st.divider()
            st.link_button("📊 查看 DIX / GEX (暗池)", "https://squeezemetrics.com/monitor/dix")

    # ==========================================
    # 模式 A: 總覽雷達 (Macro Radar)
    # ==========================================
    if not selected_ticker:
        st.markdown("### 📡 持倉總覽雷達 (Macro Radar)")
        st.caption("自動掃描所有「持倉 (Holding)」標的，並依財報日期排序，掌握前線戰況。")
        
        holdings = portfolio_df[portfolio_df['Type'] == 'Holding']
        if holdings.empty:
            st.info("尚無持倉紀錄，請至「庫存管理」新增！")
        else:
            with st.spinner("📡 啟動雷達掃描中，擷取最新戰況..."):
                radar_data = []
                for _, row in holdings.iterrows():
                    t = row['Ticker']
                    c = row['Cost']
                    df_t = get_stock_data(t, period="1mo")
                    e_date = get_earnings_date(t)
                    
                    p = df_t['Close'].iloc[-1] if df_t is not None else 0
                    pl_pct = ((p - c) / c * 100) if c > 0 else 0
                    pl_val = p - c if c > 0 else 0
                    
                    days_left = 999
                    e_str = "N/A"
                    if e_date:
                        try:
                            days_left = (e_date - date.today()).days
                            e_str = f"{e_date.strftime('%Y-%m-%d')} ({days_left}天)"
                        except: pass
                        
                    radar_data.append({
                        "代碼": t,
                        "成本價": c,
                        "最新價": p,
                        "損益金額": pl_val,
                        "報酬率 (%)": pl_pct,
                        "下次財報": e_str,
                        "_days": days_left # 隱藏排序用
                    })
                
                if radar_data:
                    radar_df = pd.DataFrame(radar_data).sort_values("_days").drop(columns=["_days"])
                    
                    def color_pl(val):
                        if isinstance(val, str): return ''
                        if val > 0: return 'color: #00FF00;'
                        elif val < 0: return 'color: #FF4136;'
                        return ''

                    styled_radar = radar_df.style.format({
                        "成本價": "${:.2f}", "最新價": "${:.2f}", 
                        "損益金額": "${:+.2f}", "報酬率 (%)": "{:+.2f}%"
                    }).applymap(color_pl, subset=["損益金額", "報酬率 (%)"])
                    
                    st.dataframe(styled_radar, use_container_width=True, hide_index=True)

    # ==========================================
    # 模式 B: 單一股票戰術分析
    # ==========================================
    else:
        df = get_stock_data(selected_ticker, time_range)
        shares_df, shares_yoy = get_shares_data(selected_ticker)
        earnings_date = get_earnings_date(selected_ticker)
        inst_own, short_pct = get_smart_money_data(selected_ticker) 
        
        if df is not None and not df.empty:
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            price = latest['Close']
            change = price - prev['Close']
            pct_change = (change / prev['Close']) * 100
            
            # --- 🎯 2x2 網格情報卡片 ---
            row1_col1, row1_col2 = st.columns(2)
            with row1_col1:
                with st.container(border=True):
                    st.markdown("📉 **即時行情**")
                    m1, m2 = st.columns(2)
                    m1.metric("現價", f"{price:.2f}", f"{change:.2f} ({pct_change:.2f}%)")
                    m2.metric("EMA 20", f"{latest['EMA_20']:.2f}")
            with row1_col2:
                with st.container(border=True):
                    st.markdown("💼 **部位狀態**")
                    if cost_basis:
                        pl = price - cost_basis
                        pl_pct = (pl / cost_basis) * 100
                        st.metric("持倉損益", f"{pl_pct:+.2f}%", f"{pl:+.2f}", delta_color="normal" if pl > 0 else "inverse")
                    else:
                        st.metric("目前狀態", "👀 觀察清單", "")

            row2_col1, row2_col2 = st.columns(2)
            days_to_earnings = -1
            with row2_col1:
                with st.container(border=True):
                    st.markdown("🏢 **企業情報**")
                    i1, i2 = st.columns(2)
                    if earnings_date:
                        try:
                            days_to_earnings = (earnings_date - date.today()).days
                            i1.metric("下次財報", f"{earnings_date.strftime('%m/%d')}", f"{days_to_earnings} 天後" if days_to_earnings >= 0 else "剛發布", delta_color="off")
                        except: i1.metric("下次財報", f"{earnings_date}")
                    else: i1.metric("下次財報", "N/A")

                    if shares_yoy is not None and shares_yoy != 0:
                        i2.metric("股本趨勢", f"{shares_yoy:.2f}%", "縮減" if shares_yoy < 0 else "稀釋", delta_color="normal" if shares_yoy < 0 else "inverse")
                    elif shares_yoy == 0: i2.metric("股本趨勢", "持平", "")
                    else: i2.metric("股本趨勢", "N/A", "")

            with row2_col2:
                with st.container(border=True):
                    st.markdown("🐋 **籌碼動向**")
                    s1, s2 = st.columns(2)
                    s1.metric("機構持股", f"{inst_own:.1f}%" if inst_own else "N/A")
                    if short_pct is not None:
                        s2.metric("空單比例", f"{short_pct:.2f}%", "🔥 高空單" if short_pct > 10 else "正常", delta_color="inverse" if short_pct > 10 else "off")
                    else: s2.metric("空單比例", "N/A")

            # --- 🤖 AI 戰術判定徽章 ---
            judgments = []
            if price > latest['EMA_20']: judgments.append("🟢 **站穩月線**：價格在 EMA 20 之上，短線趨勢偏多。")
            else: judgments.append("🔴 **跌破月線**：價格落於 EMA 20 之下，短線趨勢轉弱。")
            
            if shares_yoy is not None and shares_yoy < 0: judgments.append("🟢 **護城河深**：公司正在回購自家股票，籌碼面安定。")
            elif shares_yoy is not None and shares_yoy > 0: judgments.append("🔴 **股權稀釋**：流通股數增加，注意潛在賣壓。")
            
            if 0 <= days_to_earnings <= 14: judgments.append(f"🟡 **財報警戒**：距離開獎僅剩 {days_to_earnings} 天，嚴防 IV (隱含波動率) 雙殺。")
            
            if inst_own is not None and inst_own > 50: judgments.append("🟢 **巨鯨護盤**：機構持股過半，長線底氣充足。")
            if short_pct is not None and short_pct > 10: judgments.append("🔥 **軋空潛力**：空單比例過高，若遇利多易引發軋空。")

            st.info(" **🎯 戰術系統判定：**\n" + "\n".join([f"- {j}" for j in judgments]))
            st.write("")

            # --- 🗂️ 垂直降噪：分頁設計 (Tabs) ---
            tab_tech, tab_moat, tab_whale = st.tabs(["📈 技術狙擊 (Price Action)", "🛡️ 護城河掃描 (Buyback)", "🐋 巨鯨聲納 (13F Holders)"])
            
            # [分頁 1] 技術狙擊
            with tab_tech:
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
                fig.add_trace(go.Candlestick(x=df['Date'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"), row=1, col=1)
                if cost_basis: fig.add_hline(y=cost_basis, line_dash="dash", line_color="yellow", annotation_text="COST", row=1, col=1)
                fig.add_trace(go.Scatter(x=df['Date'], y=df['EMA_20'], name="EMA 20", line=dict(color='#00FF00', width=1.5)), row=1, col=1)
                fig.add_trace(go.Scatter(x=df['Date'], y=df['EMA_50'], name="EMA 50", line=dict(color='#FFA500', width=1.5)), row=1, col=1)
                fig.add_trace(go.Scatter(x=df['Date'], y=df['EMA_200'], name="EMA 200", line=dict(color='#FF0000', width=1.5)), row=1, col=1)
                colors = ['#00FF00' if v >= 0 else '#FF0000' for v in df['Hist']]
                fig.add_trace(go.Bar(x=df['Date'], y=df['Hist'], name="Histogram", marker_color=colors), row=2, col=1)
                fig.add_trace(go.Scatter(x=df['Date'], y=df['MACD'], name="MACD", line=dict(color='#00FFFF', width=1.5)), row=2, col=1)
                fig.add_trace(go.Scatter(x=df['Date'], y=df['Signal'], name="Signal", line=dict(color='#FF00FF', width=1.5)), row=2, col=1)
                fig.update_layout(height=600, hovermode="x unified", template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(t=10, b=10))
                st.plotly_chart(fig, use_container_width=True)
            
            # [分頁 2] 護城河掃描
            with tab_moat:
                if shares_df is not None:
                    st.caption(f"數據來源：{selected_ticker} 季度/年度 財報 (Share Issued)")
                    fig_buyback = make_subplots(specs=[[{"secondary_y": True}]])
                    fig_buyback.add_trace(go.Scatter(x=df['Date'], y=df['Close'], name="股價 (Price)", line=dict(color='#00FFFF', width=2)), secondary_y=False)
                    fig_buyback.add_trace(go.Scatter(x=shares_df.index, y=shares_df['Shares'], name="流通股數 (Shares)", line=dict(color='#FFA500', width=3, shape='hv'), mode='lines+markers', marker=dict(size=6)), secondary_y=True)
                    fig_buyback.update_layout(template="plotly_dark", height=500, hovermode="x unified", legend=dict(orientation="h", y=1.1, x=0), margin=dict(t=10, b=10))
                    fig_buyback.update_yaxes(title_text="股價 Price", secondary_y=False)
                    min_shares, max_shares = shares_df['Shares'].min(), shares_df['Shares'].max()
                    padding = (max_shares - min_shares) * 0.2 if max_shares != min_shares else max_shares * 0.01
                    fig_buyback.update_yaxes(title_text="流通股數 Shares", secondary_y=True, showgrid=False, range=[min_shares - padding, max_shares + padding])
                    st.plotly_chart(fig_buyback, use_container_width=True)
                else:
                    st.info("缺乏流通股數歷史資料。")
            
            # [分頁 3] 巨鯨聲納
            with tab_whale:
                inst_holders_df = get_institutional_holders(selected_ticker)
                if inst_holders_df is not None:
                    st.caption(f"數據來源：{selected_ticker} 最新 13F 申報")
                    display_df = inst_holders_df.copy()
                    if 'pctHeld' in display_df.columns: display_df['pctHeld'] = display_df['pctHeld'] * 100
                    if 'pctChange' in display_df.columns: display_df['pctChange'] = display_df['pctChange'] * 100
                    if 'Date Reported' in display_df.columns: display_df['Date Reported'] = pd.to_datetime(display_df['Date Reported']).dt.strftime('%Y-%m-%d')
                    
                    rename_map = {"Date Reported": "申報日期", "Holder": "機構名稱", "pctHeld": "持股比例 (%)", "Shares": "持有股數", "Value": "市值 (USD)", "pctChange": "增減比例 (%)"}
                    display_df = display_df.rename(columns=rename_map)
                    
                    def highlight_change(val):
                        if pd.isna(val): return ''
                        if isinstance(val, (int, float)):
                            if val > 0: return 'color: #00FF00;'
                            elif val < 0: return 'color: #FF4136;'
                        return ''

                    format_dict = {k: v for k, v in {"持股比例 (%)": "{:.2f}%", "增減比例 (%)": "{:+.2f}%", "持有股數": "{:,.0f}", "市值 (USD)": "${:,.0f}"}.items() if k in display_df.columns}
                    styled_df = display_df.style.format(format_dict)
                    if "增減比例 (%)" in display_df.columns: styled_df = styled_df.applymap(highlight_change, subset=["增減比例 (%)"])
                    st.dataframe(styled_df, use_container_width=True, hide_index=True)
                else:
                    st.info("無巨鯨 13F 申報資料。")
                    
        else: st.warning(f"⚠️ 找不到 **{selected_ticker}** 的數據。")
