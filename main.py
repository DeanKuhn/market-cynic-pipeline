import json
import os
import asyncio
import sys
from src.ingestion.yahoo_probe import run_probe
from src.transformation.cleaner import clean_raw_data

# Define paths
RAW_DATA_PATH = "data/raw_stocks.json"
CLEAN_DATA_PATH = "data/cleansed_stocks.parquet"

async def run_pipeline():
    print("--- Starting Market Cynic Pipeline ---")

    # Task 1: Ingestion
    print("[1/2] Ingesting data from Yahoo Finance...")
    try:
        # Await the scraper we built earlier
        await run_probe(RAW_DATA_PATH)

        # Gatekeeper check
        if not is_file_valid(RAW_DATA_PATH):
            print("CRITICAL FALIURE: Ingestion returned no data. Terminating.")
            sys.exit(1)

    except Exception as e:
        print(f"CRITIAL FALIURE during Ingestion: {e}")
        sys.exit(1)

    # Task 2: Transformation
    print("[2/2] Cleaning and validating data...")
    try:
        # Synchronous, no need for await
        clean_raw_data(RAW_DATA_PATH, CLEAN_DATA_PATH)
    except Exception as e:
        print(f"CRITICAL FALIURE during Transformation: {e}")
        sys.exit(1)

    print("--- Pipeline Completed Successfully ---")

def is_file_valid(filepath: str) -> bool:
    # Check if file exists and has a greater size than 0
    if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
        return False

    # Check if the content is actually data (not just an empty list)
    with open(filepath, "r") as f:
        data = json.load(f)
        return len(data) > 0

if __name__ == "__main__":
    asyncio.run(run_pipeline())