import streamlit as st # type:ignore
import pandas as pd
import plotly.express as px # type:ignore
import plotly.graph_objects as go # type:ignore

st.set_page_config(page_title="Market Cynic Terminal", layout="wide", page_icon="📉")

# Custom CSS to match the "Cynic" aesthetic
st.markdown("""
    <style>
    .stMetric { background-color: #0e1117; padding: 15px; border-radius: 10px;
            border: 1px solid #31333f; }
    </style>
    """, unsafe_allow_html=True)

st.title("🕵️ Market Cynic Terminal")
st.markdown("Filtering out the noise to find where the *credible* "\
            "sentiment meets the market.")

@st.cache_data(ttl=3600) # Refresh cache every hour
def load_data():
    df = pd.read_parquet("data/market_history.parquet")
    df["run_timestamp"] = pd.to_datetime(df["run_timestamp"])
    return df

try:
    df = load_data()
except Exception as e:
    st.error("History file not found or corrupted. Let the pipeline run first!")
    st.stop()

# --- Sidebar ---
ticker = st.sidebar.selectbox("Focus Ticker", options=df["symbol"].unique())
filtered_df = df[df["symbol"] == ticker].sort_values("run_timestamp")

# --- KPI Metrics ---
last_row = filtered_df.iloc[-1]
prev_row = filtered_df.iloc[-2] if len(filtered_df) > 1 else last_row

col1, col2, col3, col4 = st.columns(4)
col1.metric("Price", f"${last_row['price']:.2f}",
            f"{(last_row['price']-prev_row['price']):.2f}")
# Show the weighted sentiment
col2.metric("Weighted Sentiment", f"{last_row['sentiment']:.2f}",
            f"{(last_row['sentiment']-prev_row['sentiment']):.2f}")
col3.metric("Engagement (Comments)", int(last_row['total_comments']))
col4.metric("Controversy Ratio", f"{last_row['avg_upvote_ratio']:.2%}")

# --- Primary Dual-Axis Chart ---
st.subheader(f"Price vs. Credible Sentiment: {ticker}")

fig = go.Figure()

# Add Price
fig.add_trace(go.Scatter(x=filtered_df["run_timestamp"], y=filtered_df["price"],
        mode='lines+markers', name='Price', line=dict(color='#00ffcc', width=3)))

# Add Weighted Sentiment on secondary Y-axis
fig.add_trace(go.Scatter(x=filtered_df["run_timestamp"], y=filtered_df["sentiment"],
                    mode='lines', name='Cynic Sentiment',
                    line=dict(color='#ff3366', dash='dot'),
                    yaxis="y2"))

fig.update_layout(
    yaxis=dict(title="Stock Price ($)"),
    yaxis2=dict(title="Weighted Sentiment Score", overlaying="y", side="right"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    template="plotly_dark"
)
st.plotly_chart(fig, use_container_width=True)

# --- The Cynic's Verdict (Logic Check) ---
st.divider()
c1, c2 = st.columns([1, 2])

with c1:
    st.subheader("The Verdict")
    if last_row.get("divergence_flag") == 1:
        st.warning("⚠️ DIVERGENCE DETECTED")
        st.write("Sentiment is rising while price is falling. This suggests "\
                 "a potential 'Bagholder' scenario where the crowd is high "\
                    "on hopium but the market is exiting.")
    else:
        st.success("✅ Alignment")
        st.write("Price and sentiment are moving in relative harmony.")

with c2:
    # Correlation Analysis
    if len(filtered_df) > 5:
        corr = filtered_df["price"].corr(filtered_df["sentiment"])
        st.write(f"Historical Correlation: **{corr:.2f}**")

        # Volatility Check
        vol = last_row.get("sentiment_volatility", 0)
        if vol < 0.1:
            st.info("📢 **Echo Chamber Alert**: Sentiment volatility is "\
                    "extremely low. The subreddit may be reaching a consensus, "\
                        "which often precedes a reversal.")