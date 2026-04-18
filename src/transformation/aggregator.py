import pandas as pd
import numpy as np
import os
from datetime import datetime, timezone
from src.ingestion.reddit_sentinel import get_reddit_data

from src.utils.logger import setup_logger
logger = setup_logger("MarketDataAggregator")

# How much to trust each subreddit's sentiment signal
# Lower = more speculative/meme-driven, higher = more fundamentals-focused
SUBREDDIT_TRUST = {
    "investing": 1.5,
    "stocks": 1.2,
    "stockmarket": 1.0,
    "wallstreetbets": 0.7,
}

def aggregate_market_data():
    logger.info("Starting Gold Layer Aggregation...")

    # Load "silver" layer (Yahoo clean data)
    silver_path = "data/cleansed_stocks.parquet"
    if not os.path.exists(silver_path):
        logger.error(f"Error: {silver_path} not found.  Run scraper first.")
        return

    df_silver = pd.read_parquet(silver_path)
    tickers = df_silver["symbol"].tolist()

    # Create a dictionary mapping symbols to prices for reddit_sentinel use
    current_prices = dict(zip(df_silver["symbol"], df_silver["price"]))

    # Reddit objects are now a list of StockSchema objects
    reddit_objects = get_reddit_data(tickers, current_prices)

    if not reddit_objects:
        logger.warning("No Reddit data collected this cycle.")
        return

    # Convert Pydantic objects into a DataFrame
    df_raw_reddit = pd.DataFrame([s.model_dump() for s in reddit_objects])

    # Calculate the "Cynic Weight' for every post
    df_raw_reddit["signal_weight"] = [s.signal_weight for s in reddit_objects]
    df_raw_reddit["weighted_sentiment"] = df_raw_reddit["sentiment_score"] * \
        df_raw_reddit["signal_weight"]

    # Stage 1: Summarize per symbol+subreddit to preserve subreddit identity
    df_by_subreddit = df_raw_reddit.groupby(["symbol", "subreddit"]).agg(
        mentions=("symbol", "count"),
        avg_sentiment=("sentiment_score", "mean"),
        avg_upvote_ratio=("upvote_ratio", "mean"),
        total_comments=("num_comments", "sum"),
        total_ups=("ups", "sum"),
        total_weighted_sentiment=("weighted_sentiment", "sum"),
        total_weight=("signal_weight", "sum")
    ).reset_index()

    # Apply per-subreddit trust multiplier before collapsing
    df_by_subreddit["trust_weight"] = \
        df_by_subreddit["subreddit"].map(SUBREDDIT_TRUST).fillna(1.0)

    df_by_subreddit["total_weighted_sentiment"] *= \
        df_by_subreddit["trust_weight"]

    df_by_subreddit["total_weight"] *= df_by_subreddit["trust_weight"]

    # Stage 2: Collapse to one row per ticker
    df_reddit_summary = df_by_subreddit.groupby("symbol").agg(
        mentions=("mentions", "sum"),
        avg_sentiment=("avg_sentiment", "mean"),
        avg_upvote_ratio=("avg_upvote_ratio", "mean"),
        total_comments=("total_comments", "sum"),
        total_ups=("total_ups", "sum"),
        total_weighted_sentiment=("total_weighted_sentiment", "sum"),
        total_weight=("total_weight", "sum")
    ).reset_index()

    # Merge with Silver (Price Data) on inner
    df_gold = pd.merge(
        df_silver[['symbol', 'price', 'volume', 'pct_change']],
        df_reddit_summary,
        on="symbol",
        how="inner"
    )

    df_gold["run_timestamp"] = datetime.now(timezone.utc)

    # Calculate the final weighted sentiment score
    df_gold["sentiment"] = df_gold["total_weighted_sentiment"] / df_gold["total_weight"]

    # Historical Tracking Logic
    history_path = "data/market_history.parquet"
    if os.path.exists(history_path):
        # Load existing history and append new run
        df_history = pd.read_parquet(history_path)
        df_final = pd.concat([df_history, df_gold], ignore_index=True)
        df_final = calculate_cynic_metrics(df_final)
    else:
        # This means it is the first time running history
        df_final = calculate_cynic_metrics(df_gold)

    # Save expanded history
    df_final.to_parquet(history_path, index=False)
    logger.info(f"History Updated: {history_path}")

def calculate_cynic_metrics(df):
    # 6-run window = ~2 days at 3 runs/day. min_periods=3 means metrics
    # start appearing after day 1 rather than waiting a full 2 days.
    WINDOW = 6
    MIN_PERIODS = 3

    df["sentiment_volatility"] = df.groupby("symbol")["sentiment"].transform(
        lambda x: x.rolling(window=WINDOW, min_periods=MIN_PERIODS).std())

    df["sentiment_momentum"] = df.groupby("symbol")["sentiment"].transform(
        lambda x: x.rolling(WINDOW, min_periods=MIN_PERIODS).mean().diff())

    df["price_momentum"] = df.groupby("symbol")["pct_change"].transform(
        lambda x: x.rolling(WINDOW, min_periods=MIN_PERIODS).mean())

    df["volume_momentum"] = df.groupby("symbol")["volume"].transform(
        lambda x: x.rolling(WINDOW, min_periods=MIN_PERIODS).mean().diff())

    # Divergence: Positive sentiment growth + Negative price trend = Danger
    df["divergence"] = np.where(
        (df["sentiment_momentum"] > 0) &
        (df["price_momentum"] < 0) &
        (df["sentiment_momentum"].notna()) &
        (df["price_momentum"].notna()),
        1, 0
    )

    return df

if __name__ == "__main__":
    aggregate_market_data()