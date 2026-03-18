import streamlit as st
import pandas as pd
from datetime import date

from data import (
    get_stock_data, get_shares_data, get_earnings_date,
    get_smart_money_data, get_institutional_holders,
    find_support_resistance,
)
from charts import build_candlestick_chart, build_buyback_chart
from config import (
    EARNINGS_WARNING_DAYS, INST_OWN_THRESHOLD,
    SHORT_SQUEEZE_THRESHOLD, SR_PROXIMITY_PCT,
)


def render_analysis(selected_ticker, cost_basis, time_range):
    """Render the single-stock tactical analysis view."""
    df = get_stock_data(selected_ticker, time_range)
    shares_df, shares_yoy = get_shares_data(selected_ticker)
    earnings_date = get_earnings_date(selected_ticker)
    inst_own, short_pct = get_smart_money_data(selected_ticker)

    if df is None or df.empty:
        st.warning(f"⚠️ 找不到 **{selected_ticker}** 的數據。")
        return

    latest = df.iloc[-1]
    prev = df.iloc[-2]
    price = latest['Close']
    change = price - prev['Close']
    pct_change = (change / prev['Close']) * 100

    # --- 2x2 info cards ---
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
                except:
                    i1.metric("下次財報", f"{earnings_date}")
            else:
                i1.metric("下次財報", "N/A")

            if shares_yoy is not None and shares_yoy != 0:
                i2.metric("股本趨勢", f"{shares_yoy:.2f}%", "縮減" if shares_yoy < 0 else "稀釋", delta_color="normal" if shares_yoy < 0 else "inverse")
            elif shares_yoy == 0:
                i2.metric("股本趨勢", "持平", "")
            else:
                i2.metric("股本趨勢", "N/A", "")

    with row2_col2:
        with st.container(border=True):
            st.markdown("🐋 **籌碼動向**")
            s1, s2 = st.columns(2)
            s1.metric("機構持股", f"{inst_own:.1f}%" if inst_own else "N/A")
            if short_pct is not None:
                s2.metric("空單比例", f"{short_pct:.2f}%", "🔥 高空單" if short_pct > SHORT_SQUEEZE_THRESHOLD else "正常", delta_color="inverse" if short_pct > SHORT_SQUEEZE_THRESHOLD else "off")
            else:
                s2.metric("空單比例", "N/A")

    # --- AI judgment badges ---
    judgments = []

    # EMA 20 (short-term)
    if price > latest['EMA_20']:
        judgments.append("🟢 **站穩月線**：價格在 EMA 20 之上，短線趨勢偏多。")
    else:
        judgments.append("🔴 **跌破月線**：價格落於 EMA 20 之下，短線趨勢轉弱。")

    # EMA 200 (long-term)
    if price > latest['EMA_200']:
        judgments.append("🟢 **長線多頭**：價格站穩年線 (EMA 200)，大趨勢向上。")
    else:
        judgments.append("🔴 **長線空頭**：價格跌破年線 (EMA 200)，大趨勢偏弱。")

    # MA alignment
    if latest['EMA_20'] > latest['EMA_50'] > latest['EMA_200']:
        judgments.append("🟢 **多頭排列**：短 > 中 > 長均線完美排列，趨勢強勁。")
    elif latest['EMA_20'] < latest['EMA_50'] < latest['EMA_200']:
        judgments.append("🔴 **空頭排列**：短 < 中 < 長均線全面壓制，趨勢疲弱。")

    # S/R proximity
    supports, resistances = find_support_resistance(df)
    for i, r in enumerate(resistances[:1]):
        dist = abs(price - r) / r * 100
        if dist <= SR_PROXIMITY_PCT:
            judgments.append(f"🟡 **接近壓力**：價格距離壓力位 R{i+1} (${r:.2f}) 僅 {dist:.1f}%，注意突破或回落。")
    for i, s in enumerate(supports[:1]):
        dist = abs(price - s) / s * 100
        if dist <= SR_PROXIMITY_PCT:
            judgments.append(f"🟢 **守穩支撐**：價格距離支撐位 S{i+1} (${s:.2f}) 僅 {dist:.1f}%，留意反彈機會。")

    # Buyback / dilution
    if shares_yoy is not None and shares_yoy < 0:
        judgments.append("🟢 **護城河深**：公司正在回購自家股票，籌碼面安定。")
    elif shares_yoy is not None and shares_yoy > 0:
        judgments.append("🔴 **股權稀釋**：流通股數增加，注意潛在賣壓。")

    # Earnings alert
    if 0 <= days_to_earnings <= EARNINGS_WARNING_DAYS:
        judgments.append(f"🟡 **財報警戒**：距離開獎僅剩 {days_to_earnings} 天，嚴防 IV (隱含波動率) 雙殺。")

    # MACD cross
    macd_cross_up = latest['MACD'] > latest['Signal'] and prev['MACD'] <= prev['Signal']
    macd_cross_down = latest['MACD'] < latest['Signal'] and prev['MACD'] >= prev['Signal']
    if macd_cross_up:
        judgments.append("🟢 **MACD 金叉**：動能指標交叉向上，短線買盤增強。")
    elif macd_cross_down:
        judgments.append("🔴 **MACD 死叉**：動能指標交叉向下，短線賣壓升溫。")

    # Institutional ownership
    if inst_own is not None and inst_own > INST_OWN_THRESHOLD:
        judgments.append("🟢 **巨鯨護盤**：機構持股過半，長線底氣充足。")
    # Short squeeze
    if short_pct is not None and short_pct > SHORT_SQUEEZE_THRESHOLD:
        judgments.append("🔥 **軋空潛力**：空單比例過高，若遇利多易引發軋空。")

    st.info(" **🎯 戰術系統判定：**\n" + "\n".join([f"- {j}" for j in judgments]))
    st.write("")

    # --- Tabs: Tech / Buyback / Whale ---
    tab_tech, tab_moat, tab_whale = st.tabs([
        "📈 技術狙擊 (Price Action)",
        "🛡️ 護城河掃描 (Buyback)",
        "🐋 巨鯨聲納 (13F Holders)",
    ])

    with tab_tech:
        fig = build_candlestick_chart(df, cost_basis)
        st.plotly_chart(fig, use_container_width=True)

    with tab_moat:
        if shares_df is not None:
            st.caption(f"數據來源：{selected_ticker} 季度/年度 財報 (Share Issued)")
            fig_buyback = build_buyback_chart(df, shares_df)
            st.plotly_chart(fig_buyback, use_container_width=True)
        else:
            st.info("缺乏流通股數歷史資料。")

    with tab_whale:
        _render_whale_tab(selected_ticker)


def _render_whale_tab(ticker):
    """Render the institutional holders (13F) tab."""
    inst_holders_df = get_institutional_holders(ticker)
    if inst_holders_df is None:
        st.info("無巨鯨 13F 申報資料。")
        return

    st.caption(f"數據來源：{ticker} 最新 13F 申報")
    display_df = inst_holders_df.copy()
    if 'pctHeld' in display_df.columns:
        display_df['pctHeld'] = display_df['pctHeld'] * 100
    if 'pctChange' in display_df.columns:
        display_df['pctChange'] = display_df['pctChange'] * 100
    if 'Date Reported' in display_df.columns:
        display_df['Date Reported'] = pd.to_datetime(display_df['Date Reported']).dt.strftime('%Y-%m-%d')

    rename_map = {
        "Date Reported": "申報日期", "Holder": "機構名稱",
        "pctHeld": "持股比例 (%)", "Shares": "持有股數",
        "Value": "市值 (USD)", "pctChange": "增減比例 (%)",
    }
    display_df = display_df.rename(columns=rename_map)

    def highlight_change(val):
        if pd.isna(val):
            return ''
        if isinstance(val, (int, float)):
            if val > 0:
                return 'color: #00FF00;'
            elif val < 0:
                return 'color: #FF4136;'
        return ''

    format_dict = {
        k: v for k, v in {
            "持股比例 (%)": "{:.2f}%", "增減比例 (%)": "{:+.2f}%",
            "持有股數": "{:,.0f}", "市值 (USD)": "${:,.0f}",
        }.items() if k in display_df.columns
    }
    styled_df = display_df.style.format(format_dict)
    if "增減比例 (%)" in display_df.columns:
        styled_df = styled_df.map(highlight_change, subset=["增減比例 (%)"])
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
