import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import date

from data import get_stock_data, get_shares_data, get_earnings_date, get_smart_money_data, get_institutional_holders
from analysis import find_support_resistance, compute_judgments


def _render_info_cards(price, change, pct_change, latest, cost_basis, earnings_date, shares_yoy, inst_own, short_pct):
    """Render the 2x2 info card grid. Returns days_to_earnings for use by judgments."""
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

    days_to_earnings = -1
    row2_col1, row2_col2 = st.columns(2)
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

    return days_to_earnings


def _render_sr_card(price, sr_levels):
    """Render the Support / Resistance info card."""
    with st.container(border=True):
        st.markdown("🛡️ **關鍵支撐 / 壓力區間**")
        sr_col1, sr_col2 = st.columns(2)
        with sr_col1:
            st.markdown("**🟢 支撐 (Support)**")
            if sr_levels['support']:
                for lvl_price, strength in sr_levels['support']:
                    dist = ((price - lvl_price) / price) * 100
                    bars = "█" * min(strength, 8)
                    st.markdown(f"  `${lvl_price:.2f}` ({dist:+.1f}%) — 強度 {bars} ({strength}次觸及)")
            else:
                st.caption("偵測範圍內無明顯支撐")
        with sr_col2:
            st.markdown("**🔴 壓力 (Resistance)**")
            if sr_levels['resistance']:
                for lvl_price, strength in sr_levels['resistance']:
                    dist = ((lvl_price - price) / price) * 100
                    bars = "█" * min(strength, 8)
                    st.markdown(f"  `${lvl_price:.2f}` (+{dist:.1f}%) — 強度 {bars} ({strength}次觸及)")
            else:
                st.caption("偵測範圍內無明顯壓力")


def _render_chart(df, cost_basis, sr_levels):
    """Render the candlestick + MACD chart with S/R lines."""
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
    fig.add_trace(go.Candlestick(x=df['Date'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"), row=1, col=1)
    if cost_basis: fig.add_hline(y=cost_basis, line_dash="dash", line_color="yellow", annotation_text="COST", row=1, col=1)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['EMA_20'], name="EMA 20", line=dict(color='#00FF00', width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['EMA_50'], name="EMA 50", line=dict(color='#FFA500', width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['EMA_200'], name="EMA 200", line=dict(color='#FF0000', width=1.5)), row=1, col=1)

    # Draw Support / Resistance lines
    for lvl_price, strength in sr_levels.get('support', []):
        opacity = min(0.3 + strength * 0.1, 0.9)
        fig.add_hline(
            y=lvl_price, line_dash="dot", line_color=f"rgba(0,255,100,{opacity})",
            line_width=max(1, min(strength, 4)),
            annotation_text=f"S ${lvl_price:.2f} ({strength}x)",
            annotation_position="bottom left",
            annotation_font_color="rgba(0,255,100,0.8)",
            annotation_font_size=10,
            row=1, col=1
        )
    for lvl_price, strength in sr_levels.get('resistance', []):
        opacity = min(0.3 + strength * 0.1, 0.9)
        fig.add_hline(
            y=lvl_price, line_dash="dot", line_color=f"rgba(255,65,54,{opacity})",
            line_width=max(1, min(strength, 4)),
            annotation_text=f"R ${lvl_price:.2f} ({strength}x)",
            annotation_position="top left",
            annotation_font_color="rgba(255,65,54,0.8)",
            annotation_font_size=10,
            row=1, col=1
        )

    colors = ['#00FF00' if v >= 0 else '#FF0000' for v in df['Hist']]
    fig.add_trace(go.Bar(x=df['Date'], y=df['Hist'], name="Histogram", marker_color=colors), row=2, col=1)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['MACD'], name="MACD", line=dict(color='#00FFFF', width=1.5)), row=2, col=1)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['Signal'], name="Signal", line=dict(color='#FF00FF', width=1.5)), row=2, col=1)
    fig.update_layout(height=650, hovermode="x unified", template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)


def _render_buyback_tab(selected_ticker, shares_df, df):
    """Render the Buyback Scanner tab."""
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


def _render_whale_tab(selected_ticker):
    """Render the Whale Sonar (13F Holders) tab."""
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


def render_stock_view(selected_ticker, time_range, cost_basis):
    """Render the full single-stock tactical analysis view."""
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

        sr_levels = find_support_resistance(df, window=20, num_levels=3)

        # Info cards
        days_to_earnings = _render_info_cards(price, change, pct_change, latest, cost_basis, earnings_date, shares_yoy, inst_own, short_pct)

        # S/R card
        _render_sr_card(price, sr_levels)

        # AI judgment badges
        judgments = compute_judgments(price, latest['EMA_20'], sr_levels, shares_yoy, days_to_earnings, inst_own, short_pct)
        st.info(" **🎯 戰術系統判定：**\n" + "\n".join([f"- {j}" for j in judgments]))
        st.write("")

        # Tabbed analysis views
        tab_tech, tab_moat, tab_whale = st.tabs(["📈 技術狙擊 (Price Action)", "🛡️ 護城河掃描 (Buyback)", "🐋 巨鯨聲納 (13F Holders)"])

        with tab_tech:
            _render_chart(df, cost_basis, sr_levels)

        with tab_moat:
            _render_buyback_tab(selected_ticker, shares_df, df)

        with tab_whale:
            _render_whale_tab(selected_ticker)
    else:
        st.warning(f"⚠️ 找不到 **{selected_ticker}** 的數據。")
