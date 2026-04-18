import json
import os
import asyncio
import sys
from src.utils.logger import setup_logger
from src.ingestion.yahoo_probe import run_probe
from src.transformation.cleaner import clean_raw_data
from src.transformation.aggregator import aggregate_market_data

logger = setup_logger("MainPipeline")

# Define paths
RAW_DATA_PATH = "data/raw_stocks.json"
CLEAN_DATA_PATH = "data/cleansed_stocks.parquet"

async def run_pipeline():
    logger.info("--- Starting Market Cynic Pipeline ---")

    # Task 1: Ingestion (Bronze)
    logger.info("[1/3] Ingesting data from Yahoo Finance...")
    try:
        await run_probe(RAW_DATA_PATH)
        if not is_file_valid(RAW_DATA_PATH):
            logger.error("CRITICAL FAILURE: Ingestion returned no data. Terminating.")
            sys.exit(1)

    except Exception as e:
        logger.error(f"CRITICAL FAILURE during Ingestion: {e}", exc_info=True)
        sys.exit(1)

    # Task 2: Transformation (Silver)
    logger.info("[2/3] Cleaning and validating data...")
    try:
        clean_raw_data(RAW_DATA_PATH, CLEAN_DATA_PATH)
        if not os.path.exists(CLEAN_DATA_PATH) or os.path.getsize(CLEAN_DATA_PATH) == 0:
            logger.error("TRANSFORMATION FAILED: Silver layer is empty. Terminating.")
            sys.exit(1)
    except Exception as e:
        logger.error(f"CRITICAL FAILURE during Transformation: {e}", exc_info=True)
        sys.exit(1)

    # Task 3: Aggregate with Sentiment (Gold)
    logger.info("[3/3] Aggregating data with sentiment...")
    try:
        aggregate_market_data()
        if not os.path.exists("data/market_history.parquet"):
            logger.error("CRITICAL FAILURE: Gold layer was not written. Terminating.")
            sys.exit(1)
    except Exception as e:
        logger.error(f"CRITICAL FAILURE during aggregation: {e}", exc_info=True)
        sys.exit(1)

    logger.info("--- Pipeline Completed Successfully ---")

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