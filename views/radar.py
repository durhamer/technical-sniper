import streamlit as st
import pandas as pd
from datetime import date
from concurrent.futures import ThreadPoolExecutor, as_completed

from data import get_stock_data, get_earnings_date


def _fetch_radar_row(row):
    """Fetch data for a single ticker and return a radar row dict."""
    t = row['Ticker']
    c = row['Cost']
    stock_type = "💰" if row['Type'] == 'Holding' else "👀"

    df_t = get_stock_data(t, period="2y")
    e_date = get_earnings_date(t)

    dist_pct = 0
    if df_t is not None and len(df_t) > 200:
        p = df_t['Close'].iloc[-1]
        ema200 = df_t['EMA_200'].iloc[-1]
        prev_ema200 = df_t['EMA_200'].iloc[-2]
        prev_p = df_t['Close'].iloc[-2]

        dist_pct = ((p - ema200) / ema200) * 100
        prev_dist_pct = ((prev_p - prev_ema200) / prev_ema200) * 100

        if abs(dist_pct) > abs(prev_dist_pct):
            trend = "↗️ 擴張" if dist_pct > 0 else "↘️ 遠離"
        else:
            trend = "➡️ 修正" if dist_pct > 0 else "⤴️ 回歸"

        ema_info = f"{dist_pct:+.1f}% ({trend})"
    else:
        p = 0
        ema_info = "計算中..."

    pl_pct = ((p - c) / c * 100) if c > 0 else 0

    days_left = 999
    e_str = "N/A"
    if e_date:
        try:
            days_left = (e_date - date.today()).days
            e_str = f"{e_date.strftime('%m/%d')} ({days_left}d)"
        except:
            pass

    return {
        "狀態": stock_type,
        "代碼": t,
        "最新價": p,
        "報酬率 (%)": pl_pct if row['Type'] == 'Holding' else None,
        "EMA 200 乖離 (趨勢)": ema_info,
        "下次財報 (倒數)": e_str,
        "_days": days_left,
        "_dist": dist_pct,
    }


def render_radar(portfolio_df):
    """Render the Macro Radar overview."""
    st.markdown("### 📡 全球戰術雷達 (Global Tactical Radar)")
    st.caption("同步掃描「持倉」與「關注」標的，監控 EMA 200 位階與財報倒數。")

    all_targets = portfolio_df
    if all_targets.empty:
        st.info("尚無紀錄，請至「庫存管理」新增！")
        return

    with st.spinner("📡 正在並行計算 EMA 200 乖離度與財報時程..."):
        rows = [row for _, row in all_targets.iterrows()]
        radar_data = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(_fetch_radar_row, row): row for row in rows}
            for future in as_completed(futures):
                try:
                    radar_data.append(future.result())
                except:
                    pass

        if radar_data:
            radar_df = pd.DataFrame(radar_data).sort_values("_days")

            def style_radar(styler):
                def color_earnings(val):
                    if '(' in str(val):
                        days = int(str(val).split('(')[1].split('d')[0])
                        if days <= 7:
                            return 'background-color: #8B0000; color: white'
                        if days <= 14:
                            return 'background-color: #B8860B; color: white'
                    return ''

                def color_ema(val):
                    if '+' in str(val):
                        return 'color: #00FF00;'
                    if '-' in str(val):
                        return 'color: #FF4136;'
                    return ''

                styler.map(color_earnings, subset=["下次財報 (倒數)"])
                styler.map(color_ema, subset=["EMA 200 乖離 (趨勢)"])
                styler.format({
                    "最新價": "${:.2f}",
                    "報酬率 (%)": lambda x: f"{x:+.2f}%" if pd.notnull(x) else "---",
                })
                return styler

            styled_df = radar_df.drop(columns=["_days", "_dist"]).style.pipe(style_radar)
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
