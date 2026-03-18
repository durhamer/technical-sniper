import numpy as np


def find_support_resistance(df, window=20, num_levels=3, merge_pct=0.015):
    """
    Detect support and resistance levels using local pivot highs/lows,
    then cluster nearby levels together and rank by touch count.

    Args:
        df: DataFrame with 'High', 'Low', 'Close' columns
        window: Rolling window size for detecting local extremes
        num_levels: Max number of S/R levels to return per side
        merge_pct: Percentage threshold to merge nearby levels (1.5% default)

    Returns:
        dict with 'support' and 'resistance' lists of (price, strength) tuples
    """
    if df is None or len(df) < window * 2:
        return {'support': [], 'resistance': []}

    highs = df['High'].values
    lows = df['Low'].values
    close = df['Close'].values
    current_price = close[-1]

    pivot_highs = []
    pivot_lows = []

    # Find local pivot points
    for i in range(window, len(df) - window):
        if highs[i] == max(highs[i - window:i + window + 1]):
            pivot_highs.append(highs[i])
        if lows[i] == min(lows[i - window:i + window + 1]):
            pivot_lows.append(lows[i])

    def cluster_levels(pivots, merge_threshold):
        """Merge nearby pivot points into clusters, return (avg_price, touch_count)."""
        if not pivots:
            return []
        sorted_pivots = sorted(pivots)
        clusters = []
        current_cluster = [sorted_pivots[0]]

        for p in sorted_pivots[1:]:
            if (p - current_cluster[0]) / current_cluster[0] <= merge_threshold:
                current_cluster.append(p)
            else:
                clusters.append((np.mean(current_cluster), len(current_cluster)))
                current_cluster = [p]
        clusters.append((np.mean(current_cluster), len(current_cluster)))

        clusters.sort(key=lambda x: x[1], reverse=True)
        return clusters

    all_pivots = pivot_highs + pivot_lows
    clustered = cluster_levels(all_pivots, merge_pct)

    support = [(price, strength) for price, strength in clustered if price < current_price]
    resistance = [(price, strength) for price, strength in clustered if price >= current_price]

    support = sorted(support, key=lambda x: x[1], reverse=True)[:num_levels]
    resistance = sorted(resistance, key=lambda x: x[1], reverse=True)[:num_levels]

    support.sort(key=lambda x: x[0], reverse=True)
    resistance.sort(key=lambda x: x[0])

    return {'support': support, 'resistance': resistance}


def compute_judgments(price, ema_20, sr_levels, shares_yoy, days_to_earnings, inst_own, short_pct):
    """
    Compute AI tactical judgment badges based on current stock data.

    Returns:
        list[str]: List of judgment strings with emoji prefixes.
    """
    judgments = []

    if price > ema_20:
        judgments.append("🟢 **站穩月線**：價格在 EMA 20 之上，短線趨勢偏多。")
    else:
        judgments.append("🔴 **跌破月線**：價格落於 EMA 20 之下，短線趨勢轉弱。")

    if shares_yoy is not None and shares_yoy < 0:
        judgments.append("🟢 **護城河深**：公司正在回購自家股票，籌碼面安定。")
    elif shares_yoy is not None and shares_yoy > 0:
        judgments.append("🔴 **股權稀釋**：流通股數增加，注意潛在賣壓。")

    if 0 <= days_to_earnings <= 14:
        judgments.append(f"🟡 **財報警戒**：距離開獎僅剩 {days_to_earnings} 天，嚴防 IV (隱含波動率) 雙殺。")

    if inst_own is not None and inst_own > 50:
        judgments.append("🟢 **巨鯨護盤**：機構持股過半，長線底氣充足。")
    if short_pct is not None and short_pct > 10:
        judgments.append("🔥 **軋空潛力**：空單比例過高，若遇利多易引發軋空。")

    # S/R proximity alerts
    if sr_levels['support']:
        nearest_support = sr_levels['support'][0][0]
        support_dist = ((price - nearest_support) / price) * 100
        if support_dist < 2.0:
            judgments.append(f"🟡 **逼近支撐**：距離支撐 ${nearest_support:.2f} 僅 {support_dist:.1f}%，留意止跌反彈或破底加速。")
    if sr_levels['resistance']:
        nearest_resistance = sr_levels['resistance'][0][0]
        resist_dist = ((nearest_resistance - price) / price) * 100
        if resist_dist < 2.0:
            judgments.append(f"🟡 **逼近壓力**：距離壓力 ${nearest_resistance:.2f} 僅 {resist_dist:.1f}%，留意突破或回檔。")

    return judgments
