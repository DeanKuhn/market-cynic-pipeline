from pydantic import BaseModel, Field, field_validator
from datetime import datetime, timezone
from typing import Optional, Any
import math

# Pydantic operates as a "contract" defining the shape and rules of the data
class StockSchema(BaseModel):
    # --- Identification ---
    symbol: str = Field(..., pattern=r"^[A-Z]{1,5}$")
    price: float
    name: Optional[str] = None
    volume: Optional[float] = None
    pct_change: Optional[float] = None

    # --- Post Metadata ---
    post_id: Optional[str] = None
    flair: Optional[str] = None
    subreddit: Optional[str] = None

    # --- Real-World Reddit Metadata ---
    ups: int = Field(default=0)
    upvote_ratio: float = Field(default=1.0)
    num_comments: int = Field(default=0)
    is_original_content: bool = False
    sentiment_score: float = 0.0

    # --- Temporal data ---
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("price", mode="before")
    @classmethod
    def clean_price(cls, v):
        if isinstance(v, str):
            # Get rid of the "$" before money values
            cleaned = v.replace("$", "").replace(",", "").strip()
            try:
                return float(cleaned)
            except (ValueError, TypeError):
                raise ValueError(f"Cannot parse price: {v!r}")
        if v is None:
            raise ValueError("Price cannot be None")
        return v

    @field_validator("volume", mode="before")
    @classmethod
    def clean_volume(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            cleaned = v.replace(",", "").strip()
            multipliers = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}

            # Get rid of multipliers above and multiply respectively
            for suffix, multiplier in multipliers.items():
                if cleaned.upper().endswith(suffix):
                    try:
                        return float(cleaned[:-1]) * multiplier
                    except (ValueError, TypeError):
                        raise ValueError(f"Cannot parse volume: {v!r}")
            try:
                return float(cleaned)
            except (ValueError, TypeError):
                raise ValueError(f"Cannot parse volume: {v!r}")
        return v

    @field_validator("pct_change", mode="before")
    @classmethod
    def clean_pct_change(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            # Get rid of "%" noise
            cleaned = v.replace("%", "").replace("+", "").strip()
            try:
                return float(cleaned)
            except (ValueError, TypeError):
                raise ValueError(f"Cannot parse pct_change: {v!r}")
        return v

    @field_validator("upvote_ratio")
    @classmethod
    def validate_ratio(cls, v):
        # If no upvote ratio observed, return 1.0, not 0.0
        if v is None:
            return 1.0
        return max(0.0, min(1.0, float(v)))

    @field_validator("timestamp", mode="before")
    @classmethod
    def prioritize_reddit_time(cls, v: Any):
        # If the scraper provides a UTC integer (created_utc), convert it
        # Otherwise, if it's missing or garbage, let Pydantic use the default
        if v is None:
            return datetime.now(timezone.utc)
        if isinstance(v, (int, float)):
            # Converts Reddit's 1776344457 format to a datetime object
            return datetime.fromtimestamp(v, tz=timezone.utc)
        return v

    @property
    def signal_weight(self) -> float:
        # Heuristic: High engagement density (comments vs ups)
        # and low upvote ratios increase the 'Cynic weight'

        # (1.0 - 0.86) = 0.14, the 'Controversy factor'
        controversy_factor = 1.0 - self.upvote_ratio

        # log1p prevents division by zero and dampens viral outliers
        engagement_boost = math.log1p(self.num_comments) * 0.2

        # Base weight + controversy + engagement
        weight = 1.0 + (controversy_factor * engagement_boost)
        return round(weight, 2)