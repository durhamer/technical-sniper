import streamlit as st

from portfolio import load_portfolio, save_portfolio
from views.radar import render_radar
from views.analysis import render_analysis

# --- Page config ---
st.set_page_config(page_title="戰術狙擊鏡 v7.8 (Macro Radar)", layout="wide")
st.title("🦅 戰術狙擊鏡 (Pro Edition)")

# --- Main tabs ---
tab1, tab2 = st.tabs(["📊 戰術看板", "📝 庫存管理"])

# ============================
# Tab 2: Portfolio management
# ============================
with tab2:
    st.markdown("### ☁️ 雲端庫存管理")
    current_df = load_portfolio()
    edited_df = st.data_editor(
        current_df, num_rows="dynamic", use_container_width=True,
        column_config={
            "Ticker": st.column_config.TextColumn("代碼", required=True),
            "Cost": st.column_config.NumberColumn("成本", format="$%.2f"),
            "Type": st.column_config.SelectboxColumn("狀態", options=["Holding", "Watchlist"], required=True),
            "Note": st.column_config.TextColumn("筆記"),
        },
        key="editor",
    )
    if not edited_df.equals(current_df):
        with st.spinner("同步中..."):
            save_portfolio(edited_df)
        st.success("✅ 同步完成！")
        st.rerun()

# ============================
# Tab 1: Tactical dashboard
# ============================
with tab1:
    portfolio_df = load_portfolio()
    selected_ticker = None
    time_range = "2y"
    cost_basis = None

    with st.sidebar:
        st.header("🔭 戰術導航")
        filter_type = st.radio("模式", ["全部", "💰 持倉", "👀 關注"])

        filtered_df = portfolio_df
        if filter_type == "💰 持倉":
            filtered_df = portfolio_df[portfolio_df['Type'] == 'Holding']
        elif filter_type == "👀 關注":
            filtered_df = portfolio_df[portfolio_df['Type'] == 'Watchlist']

        select_options = ["📡 總覽雷達 (Macro Radar)"]
        if not filtered_df.empty:
            select_options += filtered_df.apply(
                lambda x: f"{x['Ticker']} {'($' + str(x['Cost']) + ')' if x['Cost'] > 0 else ''}",
                axis=1,
            ).tolist()

        selected_label = st.selectbox("選擇標的", select_options)

        if selected_label == "📡 總覽雷達 (Macro Radar)":
            selected_ticker = None
        else:
            selected_ticker = selected_label.split(' ')[0]
            row = portfolio_df[portfolio_df['Ticker'] == selected_ticker].iloc[0]
            cost_basis = row['Cost'] if row['Cost'] > 0 else None
            note = row.get('Note', '')
            st.divider()
            if note:
                st.caption(f"📝 筆記: {note}")
            time_range = st.select_slider("K線範圍", options=["6mo", "1y", "2y", "5y"], value="2y")
            st.divider()
            st.link_button("📊 查看 DIX / GEX (暗池)", "https://squeezemetrics.com/monitor/dix")

        st.divider()
        with st.expander("🔧 資料源診斷"):
            test_ticker = st.text_input("測試代碼", value="AAPL", key="diag_ticker")
            if st.button("🩺 測試連線"):
                from data import get_stock_data
                import time
                start = time.time()
                with st.spinner("正在連線 Yahoo Finance..."):
                    test_df = get_stock_data(test_ticker, period="5d")
                elapsed = time.time() - start
                if test_df is not None and not test_df.empty:
                    latest = test_df.iloc[-1]
                    st.success(f"連線正常 ({elapsed:.1f}s)")
                    st.code(
                        f"代碼: {test_ticker}\n"
                        f"日期: {latest['Date'].strftime('%Y-%m-%d')}\n"
                        f"收盤: ${latest['Close']:.2f}\n"
                        f"最高: ${latest['High']:.2f}\n"
                        f"最低: ${latest['Low']:.2f}\n"
                        f"成交量: {latest['Volume']:,.0f}",
                        language=None,
                    )
                else:
                    st.error(f"連線失敗或無資料 ({elapsed:.1f}s)\n代碼 `{test_ticker}` 可能無效，或 Yahoo Finance 無回應。")

    # Route to the appropriate view
    if not selected_ticker:
        render_radar(portfolio_df)
    else:
        render_analysis(selected_ticker, cost_basis, time_range)
