import streamlit as st
import pandas as pd
from datetime import date

# 移除了 threading 和 concurrent.futures 相關的 import
from data import get_stock_data, get_earnings_date
from config import (
    MIN_EMA200_DATAPOINTS, DEFAULT_DAYS_TO_EARNINGS,
    EARNINGS_CRITICAL_DAYS, EARNINGS_WARNING_DAYS,
)

def _fetch_radar_row(row):
    """Fetch data for a single ticker and return a radar row dict."""
    t = row['Ticker']
    c = row['Cost']
    stock_type = "💰" if row['Type'] == 'Holding' else "👀"

    df_t = get_stock_data(t, period="2y")
    e_date = get_earnings_date(t)

    # 預設值
    p = 0
    dist_pct = 0
    ema_info = "計算中..."

    # 第一優先：只要 df_t 不是 None 且不為空，就絕對要把價格抓出來！
    if df_t is not None and not df_t.empty:
        p = df_t['Close'].iloc[-1]
        
        # 第二層判斷：資料夠長才計算 EMA 200 乖離
        if len(df_t) > MIN_EMA200_DATAPOINTS:
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
            ema_info = "資料不足 (上市過短)"

    pl_pct = ((p - c) / c * 100) if c > 0 else 0

    days_left = DEFAULT_DAYS_TO_EARNINGS
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

    # 改成單純的 for 迴圈循序抓取
    with st.spinner("📡 正在掃描雷達訊號 (循序加載中)..."):
        radar_data = []
        for _, row in all_targets.iterrows():
            try:
                row_data = _fetch_radar_row(row)
                radar_data.append(row_data)
            except:
                pass # 保持你原本的容錯風格

        if radar_data:
            radar_df = pd.DataFrame(radar_data).sort_values("_days")

            def style_radar(styler):
                def color_earnings(val):
                    if '(' in str(val):
                        days = int(str(val).split('(')[1].split('d')[0])
                        if days <= EARNINGS_CRITICAL_DAYS:
                            return 'background-color: #8B0000; color: white'
                        if days <= EARNINGS_WARNING_DAYS:
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
