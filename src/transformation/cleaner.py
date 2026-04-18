import json
import pandas as pd
from datetime import datetime
from src.utils.schemas import StockSchema
from pydantic import ValidationError

from src.utils.logger import setup_logger
logger = setup_logger("RawDataCleaner")

def clean_raw_data(input_file: str, output_file: str):
    with open(input_file, "r") as f:
        raw_data = json.load(f)

    valid_stocks = []
    errors = 0

    for entry in raw_data:
        # --- Key Mapping ---
        try:
            stock = StockSchema(**entry)
            valid_stocks.append(stock.model_dump())
        except ValidationError as e:
            logger.error(f"Dropping record {entry.get('symbol')}: {e}"
                         , exc_info=True)
            errors += 1

    if not valid_stocks:
        logger.error("CRITICAL ERROR: No valid stocks survived cleaning. "
                     "Check raw JSON keys.")
        df = pd.DataFrame(columns=list(StockSchema.model_fields.keys()))
    else:
        df = pd.DataFrame(valid_stocks)

    logger.info(f"Cleaning complete. Valid: {len(df)}, Dropped: {errors}")
    df.to_parquet(output_file, index=False)
    return df

if __name__ == "__main__":
    clean_raw_data("data/raw_stocks.json", "data/cleansed_stocks.parquet")