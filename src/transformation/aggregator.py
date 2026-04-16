import pandas as pd
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

    # For logging, add a unique timestamp for this iteration
    df_silver["run_timestamp"] = datetime.now()

    # Fetch fresh Reddit sentiment from "hot" pages
    tickers = df_silver["symbol"].tolist()
    reddit_stats = get_reddit_data(tickers)

    # Convert Reddit dict to DataFrame
    df_reddit = pd.DataFrame.from_dict(reddit_stats, orient="index").reset_index()
    df_reddit.columns = ["symbol", "mentions", "sentiment"]

    # Join the two DataFrames
    df_gold = pd.merge(df_silver, df_reddit, on="symbol", how="left")

    # Historical Tracking Logic
    history_path = "data/market_history.parquet"

    if os.path.exists(history_path):
        # Load existing history and append new run
        df_history = pd.read_parquet(history_path)
        df_final = pd.concat([df_history, df_gold], ignore_index=True)
        logger.info(f"Appending to history.  Total records: {len(df_final)}")
    else:
        # This means it is the first time running history
        df_final = df_gold
        logger.info("Creating new history file.")

    # Save expanded history
    df_final.to_parquet(history_path, index=False)
    logger.info(f"History Updated: {history_path}")

if __name__ == "__main__":
    aggregate_market_data()