# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the full pipeline
python -m main

# Launch the Streamlit dashboard
streamlit run src/visualization/dashboard.py

# Install dependencies (including Playwright browser)
pip install -r requirements.txt
python -m playwright install chromium --with-deps

# Docker
docker build -t market-cynic .
docker run market-cynic
```

**Important:** Always run as `python -m main`, never `python main.py`. The `-m` flag is required for absolute imports (`from src.utils...`) to resolve correctly.

The `.venv` is a Windows venv created with `uv`. In WSL, invoke it directly via `.venv/Scripts/python.exe -m main` rather than activating it.

There are no automated tests — `tests/` is empty.

## Architecture

This is a **Bronze → Silver → Gold medallion pipeline** that correlates Reddit sentiment with Yahoo Finance stock prices to detect sentiment-price divergence.

### Data Flow

1. **Bronze — Ingestion**
   - `src/ingestion/yahoo_probe.py`: Playwright headless browser scrapes Yahoo Finance "Most Active" page (JavaScript-rendered), returns top 10 stocks as JSON to `data/raw_stocks.json`.
   - `src/ingestion/reddit_sentinel.py`: Pulls the hot feed from four subreddits (r/stocks, r/wallstreetbets, r/investing, r/stockmarket) via public JSON endpoints (no API key). Filters out AutoModerator, stickied, removed, and flair-blocklisted posts. Deduplicates by `post_id`. Runs VADER sentiment analysis on post titles and maps posts to tickers by regex-matching ticker symbols. Waits 1 second between subreddits to avoid rate limiting.

2. **Silver — Cleaning** (`src/transformation/cleaner.py`): Validates `raw_stocks.json` against `StockSchema` (Pydantic), strips `$`/commas/`%` from price, volume, and pct_change strings, drops invalid records, outputs `data/cleansed_stocks.parquet`.

3. **Gold — Aggregation** (`src/transformation/aggregator.py`): Two-stage groupby:
   - **Stage 1**: Groups raw Reddit posts by `(symbol, subreddit)`, computes per-subreddit mention counts, sentiment, and weighted sentiment. Applies `SUBREDDIT_TRUST` multipliers (r/investing=1.5, r/stocks=1.2, r/stockmarket=1.0, r/wallstreetbets=0.7) to down-weight speculative sources before collapsing.
   - **Stage 2**: Collapses to one row per ticker. Inner-joins with Silver price data — tickers with no Reddit mentions are excluded entirely.
   - Appends to `data/market_history.parquet` and runs `calculate_cynic_metrics()`.

`main.py` acts as an orchestrator with a **gatekeeper pattern**: each stage is wrapped in try/except with `sys.exit(1)` on failure, and file existence is checked after Bronze and Gold to catch silent failures.

### Key Concepts

- **`signal_weight`** (defined in `src/utils/schemas.py`): `1.0 + (controversy_factor × log1p(comments) × 0.2)`. Posts with low upvote ratios and high engagement are weighted heavier — the "cynic" heuristic.
- **`SUBREDDIT_TRUST`** (defined in `src/transformation/aggregator.py`): Per-subreddit credibility multiplier applied to `total_weighted_sentiment` and `total_weight` before collapsing to per-ticker rows.
- **Divergence flag**: Set when `sentiment_momentum > 0` and `price_momentum < 0` simultaneously — the core signal the project is built around (potential bagholder scenario).
- **Rolling metrics**: 6-run window (`min_periods=3`) on the historical parquet for `sentiment_volatility`, `sentiment_momentum`, `price_momentum`, and `volume_momentum`. At 3 runs/day this spans ~2 days. Metrics start appearing after day 1.
- **`price_momentum`**: Uses the `pct_change` column (Yahoo's normalized daily % change) rather than raw price diffs — cross-ticker comparable.
- **`volume_momentum`**: Rolling diff of volume — detects surging crowd interest, amplifies divergence signal interpretation.
- **Git as database**: `data/market_history.parquet` is append-only and committed to the repo by a GitHub Actions bot (`MarketCynicBot`) on every scheduled run. Never overwrite this file — always concatenate.

### df_gold Column Layout

The Gold layer produces one row per ticker per pipeline run:

| Column | Type | Source |
|--------|------|--------|
| `symbol` | str | Yahoo / Reddit |
| `price` | float | Yahoo Silver |
| `volume` | float | Yahoo Silver |
| `pct_change` | float | Yahoo Silver |
| `mentions` | int | Reddit (sum across subreddits) |
| `avg_sentiment` | float | Reddit (mean across subreddits) |
| `avg_upvote_ratio` | float | Reddit |
| `total_comments` | int | Reddit |
| `total_ups` | int | Reddit |
| `total_weighted_sentiment` | float | Reddit (trust-adjusted) |
| `total_weight` | float | Reddit (trust-adjusted) |
| `run_timestamp` | datetime (UTC) | Pipeline |
| `sentiment` | float | `total_weighted_sentiment / total_weight` |
| `sentiment_volatility` | float | Rolling std of sentiment |
| `sentiment_momentum` | float | Rolling mean diff of sentiment |
| `price_momentum` | float | Rolling mean of pct_change |
| `volume_momentum` | float | Rolling mean diff of volume |
| `divergence` | int | 1 if sentiment↑ and price↓, else 0 |

### Deployment

GitHub Actions (`.github/workflows/schedule.yml`) runs the pipeline three times daily:
- **9:00 AM UTC** (5:00 AM ET) — pre-market baseline
- **3:00 PM UTC** (11:00 AM ET) — mid-session
- **9:30 PM UTC** (5:30 PM ET) — post-close reaction

It caches pip dependencies, installs Playwright chromium, runs `python -m main`, uploads logs as artifacts (7-day retention), does `git pull --rebase` before pushing, and commits the updated `market_history.parquet` back to `master`.
