import plotly.graph_objects as go
from plotly.subplots import make_subplots


def build_candlestick_chart(df, cost_basis=None):
    """Build the main candlestick + MACD chart."""
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        vertical_spacing=0.03, row_heights=[0.7, 0.3],
    )
    fig.add_trace(
        go.Candlestick(
            x=df['Date'], open=df['Open'], high=df['High'],
            low=df['Low'], close=df['Close'], name="Price",
        ),
        row=1, col=1,
    )
    if cost_basis:
        fig.add_hline(
            y=cost_basis, line_dash="dash", line_color="yellow",
            annotation_text="COST", row=1, col=1,
        )
    fig.add_trace(go.Scatter(x=df['Date'], y=df['EMA_20'], name="EMA 20", line=dict(color='#00FF00', width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['EMA_50'], name="EMA 50", line=dict(color='#FFA500', width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['EMA_200'], name="EMA 200", line=dict(color='#FF0000', width=1.5)), row=1, col=1)

    colors = ['#00FF00' if v >= 0 else '#FF0000' for v in df['Hist']]
    fig.add_trace(go.Bar(x=df['Date'], y=df['Hist'], name="Histogram", marker_color=colors), row=2, col=1)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['MACD'], name="MACD", line=dict(color='#00FFFF', width=1.5)), row=2, col=1)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['Signal'], name="Signal", line=dict(color='#FF00FF', width=1.5)), row=2, col=1)

    fig.update_layout(
        height=600, hovermode="x unified", template="plotly_dark",
        xaxis_rangeslider_visible=False, margin=dict(t=10, b=10),
    )
    return fig


def build_buyback_chart(df_price, shares_df):
    """Build the buyback (share count vs price) chart."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Scatter(x=df_price['Date'], y=df_price['Close'], name="股價 (Price)", line=dict(color='#00FFFF', width=2)),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=shares_df.index, y=shares_df['Shares'], name="流通股數 (Shares)",
            line=dict(color='#FFA500', width=3, shape='hv'), mode='lines+markers', marker=dict(size=6),
        ),
        secondary_y=True,
    )
    fig.update_layout(
        template="plotly_dark", height=500, hovermode="x unified",
        legend=dict(orientation="h", y=1.1, x=0), margin=dict(t=10, b=10),
    )
    fig.update_yaxes(title_text="股價 Price", secondary_y=False)
    min_shares, max_shares = shares_df['Shares'].min(), shares_df['Shares'].max()
    padding = (max_shares - min_shares) * 0.2 if max_shares != min_shares else max_shares * 0.01
    fig.update_yaxes(title_text="流通股數 Shares", secondary_y=True, showgrid=False, range=[min_shares - padding, max_shares + padding])
    return fig
