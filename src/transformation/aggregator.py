import pandas as pd
import numpy as np
import os
from datetime import datetime
from src.ingestion.reddit_sentinel import get_reddit_data

from src.utils.logger import setup_logger
logger = setup_logger("MarketDataAggregator")

def aggregate_market_data():
    logger.info("Starting Gold Layer Aggregation...")

    # Load "silver" layer (Yahoo clean data)
    silver_path = "data/cleansed_stocks.parquet"
    if not os.path.exists(silver_path):
        logger.error(f"Error: {silver_path} not found.  Run scraper first.")
        return

    df_silver = pd.read_parquet(silver_path)
    tickers = df_silver["symbol"].tolist()

    # Pass prices to the sentinel so it can bake the into the StockSchema
    current_prices = dict(zip(df_silver["symbol"], df_silver["price"]))

    # Reddit objects are now a list of StockSchema objects
    reddit_objects = get_reddit_data(tickers, current_prices)

    if not reddit_objects:
        logger.warning("No Reddit data collected this cycle.")
        return

    # 1. convert Pydantic objects into a DataFrame
    df_raw_reddit = pd.DataFrame([s.model_dump() for s in reddit_objects])

    # 2. Calculate the "Cynic Weight' for every post
    df_raw_reddit["signal_weight"] = [s.signal_weight for s in reddit_objects]
    df_raw_reddit["weighted_sentiment"] = df_raw_reddit["sentiment_score"] * \
        df_raw_reddit["signal_weight"]

    # 1. Group raw reddit data into a summary
    df_reddit_summary = df_raw_reddit.groupby("symbol").agg(
        mentions=("symbol", "count"),
        avg_sentiment=("sentiment_score", "mean"),
        avg_upvote_ratio=("upvote_ratio", "mean"),
        total_comments=("num_comments", "sum"),
        total_ups=("ups", "sum")
    ).reset_index()

    # 2. Merge with Silver (Price Data)
    # Only keep 'symbol', 'price', and 'run_timestamp' from silver
    # to prevent duplicates like 'name_x' and 'name_y'
    df_gold = pd.merge(
        df_silver[['symbol', 'price']],
        df_reddit_summary,
        on="symbol",
        how="left"
    )

    # 3. Handle the NaN values for stocks not mentioned on Reddit
    df_gold["mentions"] = df_gold["mentions"].fillna(0)
    df_gold["avg_sentiment"] = df_gold["avg_sentiment"].fillna(0)
    df_gold["run_timestamp"] = datetime.now()

    # Calculate the final weighted sentiment score
    df_gold["sentiment"] = df_gold["total_weighted_sentiment"] / df_gold["total_weight"]

    # Merge back with silver (price data)
    df_gold = pd.merge(df_silver, df_gold, on="symbol", how="left")
    df_gold["run_timestamp"] = datetime.utcnow()

    # 4. Historical Tracking Logic
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
    # 1. Volatility of Sentiment (Echo Chamber Check)
    df["sentiment_volatility"] = df.groupby("symbol")["sentiment"].transform(
        lambda x: x.rolling(window=3, min_periods=3).std())

    # 2. Sentiment Price Gap
    df["sentiment_momentum"] = df.groupby("symbol")["sentiment"].transform(
        lambda x: x.rolling(3).mean().diff())

    df["price_momentum"] = df.groupby("symbol")["price"].transform(
        lambda x: x.rolling(3).mean().diff())

    # Divergence: Positive sentiment growth + Negative price growth = Danger
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