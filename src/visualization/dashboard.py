import streamlit as st # type:ignore
import pandas as pd
import plotly.express as px # type:ignore

st.set_page_config(page_title="Market Cynic Terminal", layout="wide")

st.title("Market Cynic: Price vs. Hype")
st.markdown("Analyzing the intersection of Wall Street and the Reddit Hivemend.")

# 1. Load Data
@st.cache_data
def load_data():
    df = pd.read_parquet("data/market_history.parquet")
    df["run_timestamp"] = pd.to_datetime(df["run_timestamp"])
    return df

df = load_data()

# 2. Sidebar Filters
ticker = st.sidebar.selectbox("Select a Ticker", options=df["symbol"].unique())
filtered_df = df[df["symbol"] == ticker].sort_values("run_timestamp")

# 3. Metrics
last_price = filtered_df["price"].iloc[-1]
last_sent = filtered_df["sentiment"].iloc[-1]
mentions= filtered_df["mentions"].iloc[-1]

col1, col2, col3 = st.columns(3)
col1.metric("Current Price", f"{last_price:.2f}")
col2.metric("Reddit Sentiment", f"{last_sent:.2f}")
col3.metric("Hot Mentions", int(mentions))

# 4. Charts
st.subheader(f"Historical Trends for {ticker}")

# Price Chart
fig_price = px.line(filtered_df, x="run_timestamp", y="price", title="Price Action")
st.plotly_chart(fig_price, width="stretch")

# Sentiment Chart
fig_sent = px.bar(filtered_df, x='run_timestamp', y='sentiment',
                  title="Sentiment Drift", color='sentiment',
                  color_continuous_scale='RdYlGn')

st.plotly_chart(fig_sent, width="stretch")

if len(filtered_df) > 1:
    # Calculate Pearson Correlation
    correlation = filtered_df["price"].corr(filtered_df["sentiment"])

    st.subheader("The Cynic's Verdict")
    if abs(correlation) > 0.7:
        strength = "Strong"
    elif abs(correlation) > 0.4:
        strength = "Moderate"
    else:
        strength = "Weak/No"

    st.write(f"Correlation between Price and Sentiment: **{correlation:.2f}** ({strength})")
else:
    st.write("Not enough data points yet to calculate correlation. Run the pipeline more!")