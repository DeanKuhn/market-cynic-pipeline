import json
import pandas as pd
from datetime import datetime
from src.utils.schemas import StockSchema
from pydantic import ValidationError

def clean_raw_data(input_file: str, output_file: str):
    with open(input_file, "r") as f:
        raw_data = json.load(f)

    valid_stocks = []
    errors = 0

    for entry in raw_data:
        # add "ingested_at" metadata before validating
        entry["ingested_at"] = datetime.now().isoformat()
        try:
            stock = StockSchema(**entry)
            valid_stocks.append(stock.model_dump())
        except ValidationError as e:
            print(f"Dropping record {entry.get("symbol")}: {e}")
            errors += 1

    df = pd.DataFrame(valid_stocks)
    print(f"Cleaning complete. Valid: {len(df)}, Dropped: {errors}")
    df.to_parquet(output_file)
    return df

if __name__ == "__main__":
    clean_raw_data()