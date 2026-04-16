import pandas as pd
import os
from src.ingestion.reddit_sentinel import get_reddit_data

def aggregate_market_data():
    print("Starting Gold Layer Aggregation...")

    # Load "silver" layer (Yahoo clean data)
    silver_path = "data/cleansed_stocks.parquet"
    if not os.path.exists(silver_path):
        print(f"Error: {silver_path} not found.  Run scraper first.")
        return

    df_silver = pd.read_parquet(silver_path)

    # Fetch fresh Reddit sentiment from "hot" pages
    tickers = df_silver["symbol"].tolist()
    reddit_stats = get_reddit_data(tickers)

    # Convert Reddit dict to DataFrame
    df_reddit = pd.DataFrame.from_dict(reddit_stats, orient="index").reset_index()
    df_reddit.columns = ["symbol", "mentions", "sentiment"]

    # Join the two DataFrames
    df_gold = pd.merge(df_silver, df_reddit, on="symbol", how="left")

    # Save "gold" table
    gold_path = "data/market_insight_gold.parquet"
    df_gold.to_parquet(gold_path, index=False)

    print(f"Gold Layer Created: {gold_path}")
    print(df_gold[["symbol", "price", "mentions", "sentiment"]].head())

if __name__ == "__main__":
    aggregate_market_data()