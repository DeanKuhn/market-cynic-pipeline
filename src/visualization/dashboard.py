import streamlit as st # type:ignore
import pandas as pd
import plotly.express as px # type:ignore
import plotly.graph_objects as go # type:ignore

st.set_page_config(page_title="Market Cynic Terminal", layout="wide", page_icon="📉")

st.markdown("""
    <style>
    .stMetric { background-color: #0e1117; padding: 15px; border-radius: 10px;
            border: 1px solid #31333f; }
    </style>
    """, unsafe_allow_html=True)

st.title("🕵️ Market Cynic Terminal")
st.markdown("Filtering out the noise to find where *credible* sentiment diverges from the market.")

@st.cache_data(ttl=3600)
def load_data():
    df = pd.read_parquet("data/market_history.parquet")
    df["run_timestamp"] = pd.to_datetime(df["run_timestamp"])
    return df.sort_values(["symbol", "run_timestamp"])

try:
    df = load_data()
except Exception:
    st.error("History file not found. Run the pipeline first: `python -m main`")
    st.stop()

# --- Sidebar ---
st.sidebar.header("Controls")
ticker = st.sidebar.selectbox("Focus Ticker", options=sorted(df["symbol"].unique()))
filtered_df = df[df["symbol"] == ticker].sort_values("run_timestamp")

latest = filtered_df.iloc[-1]
prev = filtered_df.iloc[-2] if len(filtered_df) > 1 else latest

# --- KPI Row ---
col1, col2, col3, col4, col5 = st.columns(5)

col1.metric(
    "Price",
    f"${latest['price']:.2f}",
    f"{latest['pct_change']:+.2f}%" if pd.notna(latest.get('pct_change')) else "N/A"
)
col2.metric(
    "Cynic Sentiment",
    f"{latest['sentiment']:.3f}",
    f"{(latest['sentiment'] - prev['sentiment']):+.3f}"
)
col3.metric(
    "Reddit Mentions",
    int(latest['mentions']),
    f"{int(latest['mentions'] - prev['mentions']):+d}"
)
col4.metric(
    "Avg Upvote Ratio",
    f"{latest['avg_upvote_ratio']:.1%}"
)
col5.metric(
    "Volume",
    f"{latest['volume']:,.0f}" if pd.notna(latest.get('volume')) else "N/A"
)

st.divider()

# --- Primary Chart: Price vs Sentiment ---
st.subheader(f"Price vs. Cynic Sentiment — {ticker}")

fig = go.Figure()

fig.add_trace(go.Scatter(
    x=filtered_df["run_timestamp"], y=filtered_df["price"],
    mode='lines+markers', name='Price',
    line=dict(color='#00ffcc', width=3)
))

fig.add_trace(go.Scatter(
    x=filtered_df["run_timestamp"], y=filtered_df["sentiment"],
    mode='lines+markers', name='Cynic Sentiment',
    line=dict(color='#ff3366', dash='dot', width=2),
    yaxis="y2"
))

# Highlight divergence points
divergence_df = filtered_df[filtered_df["divergence"] == 1]
if not divergence_df.empty:
    fig.add_trace(go.Scatter(
        x=divergence_df["run_timestamp"], y=divergence_df["price"],
        mode='markers', name='Divergence Signal',
        marker=dict(color='#ffaa00', size=12, symbol='triangle-up')
    ))

fig.update_layout(
    yaxis=dict(title="Stock Price ($)"),
    yaxis2=dict(title="Cynic Sentiment Score", overlaying="y", side="right"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    template="plotly_dark"
)
st.plotly_chart(fig, use_container_width=True)

# --- Momentum Chart ---
has_momentum = filtered_df["sentiment_momentum"].notna().any()
if has_momentum:
    st.subheader(f"Momentum Indicators — {ticker}")

    fig2 = go.Figure()

    fig2.add_trace(go.Scatter(
        x=filtered_df["run_timestamp"], y=filtered_df["sentiment_momentum"],
        mode='lines+markers', name='Sentiment Momentum',
        line=dict(color='#ff3366', width=2)
    ))

    fig2.add_trace(go.Scatter(
        x=filtered_df["run_timestamp"], y=filtered_df["price_momentum"],
        mode='lines+markers', name='Price Momentum (pct_change rolling avg)',
        line=dict(color='#00ffcc', width=2),
        yaxis="y2"
    ))

    fig2.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)

    fig2.update_layout(
        yaxis=dict(title="Sentiment Momentum"),
        yaxis2=dict(title="Price Momentum (%)", overlaying="y", side="right"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        template="plotly_dark"
    )
    st.plotly_chart(fig2, use_container_width=True)
else:
    st.info("Momentum indicators require at least 3 pipeline runs. Keep collecting data.")

st.divider()

# --- Verdict + Analysis ---
c1, c2 = st.columns([1, 2])

with c1:
    st.subheader("The Verdict")
    if latest.get("divergence") == 1:
        st.warning("⚠️ DIVERGENCE DETECTED")
        st.write(
            "Sentiment is rising while price is falling — a potential **bagholder scenario**. "
            "The crowd is bullish but the market is exiting."
        )
    else:
        st.success("✅ No Divergence")
        st.write("Price and sentiment are moving in relative harmony.")

    vol_momentum = latest.get("volume_momentum")
    if pd.notna(vol_momentum) and latest.get("divergence") == 1:
        if vol_momentum > 0:
            st.error("🔺 Volume surging during divergence — signal strengthened.")
        else:
            st.info("🔻 Volume declining during divergence — signal weakened.")

with c2:
    st.subheader("Signal Analysis")

    if len(filtered_df) > 2:
        corr = filtered_df["price"].corr(filtered_df["sentiment"])
        st.write(f"**Price / Sentiment Correlation:** {corr:.2f}")

    vol = latest.get("sentiment_volatility")
    if pd.notna(vol):
        st.write(f"**Sentiment Volatility (6-run):** {vol:.4f}")
        if vol < 0.05:
            st.info(
                "📢 **Echo Chamber Alert**: Sentiment volatility is extremely low. "
                "The subreddit may be reaching consensus — reversals often follow."
            )

    st.write(f"**Total Comments:** {int(latest['total_comments']):,}")
    st.write(f"**Total Upvotes:** {int(latest['total_ups']):,}")

st.divider()

# --- Divergence History Table ---
st.subheader("All Divergence Signals — Historical")
divergence_history = df[df["divergence"] == 1][[
    "run_timestamp", "symbol", "price", "pct_change",
    "sentiment", "sentiment_momentum", "price_momentum", "volume_momentum"
]].sort_values("run_timestamp", ascending=False)

if divergence_history.empty:
    st.write("No divergence signals recorded yet. Data is still accumulating.")
else:
    st.dataframe(divergence_history, use_container_width=True)
