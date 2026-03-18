import streamlit as st

from gas_client import load_portfolio, save_portfolio
from ui_radar import render_radar
from ui_stock import render_stock_view

# --- Page Config (must be first Streamlit command) ---
st.set_page_config(page_title="戰術狙擊鏡 v8.0 (S/R + Parallel)", layout="wide")
st.title("🦅 戰術狙擊鏡 (Pro Edition)")

# --- Main Tabs ---
tab1, tab2 = st.tabs(["📊 戰術看板", "📝 庫存管理"])

# --- Portfolio Management Tab ---
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

# --- Tactical Dashboard Tab ---
with tab1:
    portfolio_df = load_portfolio()
    selected_ticker = None
    time_range = "2y"
    cost_basis = None

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

    # --- View Dispatch ---
    if not selected_ticker:
        render_radar(portfolio_df)
    else:
        render_stock_view(selected_ticker, time_range, cost_basis)
