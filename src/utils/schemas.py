from pydantic import BaseModel, Field, field_validator

class StockSchema(BaseModel):
    symbol: str
    name: str
    price: float
    ingested_at: str

    @field_validator("price", mode="before")
    @classmethod
    def clean_price(cls, v):
        if isinstance(v, str):
            return float(v.replace("$", "").replace(",", "").strip())
        return v