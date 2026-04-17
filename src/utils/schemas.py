from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional, Any
import math

class StockSchema(BaseModel):
    # --- Identification ---
    symbol: str = Field(..., pattern=r"^[A-Z]{1,5}$")
    price: float
    name: Optional[str] = None

    # --- Real-World Reddit Metadata ---
    ups: int = Field(default=0)
    upvote_ratio: float = Field(default=1.0)
    num_comments: int = Field(default=0)
    is_original_content: bool = False
    sentiment_score: float = 0.0

    # --- Temporal data ---
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("price", mode="before")
    @classmethod
    def clean_price(cls, v):
        if isinstance(v, str):
            cleaned = v.replace("$", "").replace(",", "").strip()
            try:
                return float(cleaned)
            except (ValueError, TypeError):
                return 0.0
        return v or 0.0

    @field_validator("upvote_ratio")
    @classmethod
    def validate_ratio(cls, v):
        if v is None:
            return 1.0
        return max(0.0, min(1.0, float(v)))

    @field_validator("timestamp", mode="before")
    @classmethod
    def prioritize_reddit_time(cls, v: Any):
        # If the scraper provides a UTC integer (created_utc), convert it
        # Otherwise, if it's missing or garbage, let Pydantic use the default
        if isinstance(v, (int, float)):
            # Converts Reddit's 1776344457 format to a datetime object
            return datetime.fromtimestamp(v)
        return v # If it's already a datetime or None, pass it through

    @property
    def signal_weight(self) -> float:
        # Heuristic: High engagement density (comments vs ups)
        # and low upvote ratios increase the 'Cynic weight'

        # (1.0 - 0.86) = 0.14 'Controversy factor'
        controversy_factor = 1.0 - self.upvote_ratio

        # log1p prevents division by zero and dampens viral outliers
        engagement_boost = math.log1p(self.num_comments) * 0.2

        # Base weight + controversy + engagement
        weight = 1.0 + (controversy_factor * engagement_boost)
        return round(weight, 2)