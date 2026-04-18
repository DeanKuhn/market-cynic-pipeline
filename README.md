# Market Cynic Pipeline

A data engineering pipeline that correlates Reddit sentiment with Yahoo Finance stock prices to detect **sentiment-price divergence** — moments where retail investor enthusiasm is rising while the market is quietly exiting.

The core hypothesis: when a stock is heavily discussed with positive sentiment on Reddit *but its price is simultaneously falling*, that divergence is a signal worth watching.

> **Current Status:** Automated runs are paused pending Reddit API OAuth approval. Reddit's 2023 API changes require a manual application for research/data access from cloud infrastructure. The pipeline runs fully end-to-end locally. Scheduled GitHub Actions runs will resume once OAuth credentials are approved and integrated.

---

## Architecture

The pipeline follows a **Bronze → Silver → Gold medallion pattern**:

```
Yahoo Finance (Playwright)  ──►  raw_stocks.json        [Bronze]
Reddit (4 subreddits)       ──►  StockSchema objects

                                 cleansed_stocks.parquet  [Silver]
                                 (Pydantic validation)

                                 market_history.parquet   [Gold]
                                 (sentiment + price merged,
                                  divergence signals computed)
```

### Data Sources

- **Yahoo Finance** — Top 10 most-active stocks scraped via Playwright headless browser (JavaScript-rendered page). Captures price, volume, and daily % change.
- **Reddit** — Public hot feeds from r/stocks, r/wallstreetbets, r/investing, and r/stockmarket. VADER sentiment analysis on post titles. Filters out AutoModerator, stickied posts, removed posts, and low-signal flairs (e.g. Meme, YOLO, Gain/Loss on WSB).

### The Cynic Heuristic

Two weighting systems compound to produce a final `sentiment` score per ticker:

1. **`signal_weight`** — Per-post weight: `1.0 + (controversy_factor × log1p(comments) × 0.2)`. Posts with low upvote ratios and high engagement (controversial + viral) are weighted *heavier*, not lighter. The cynical assumption is that controversy is signal.

2. **`SUBREDDIT_TRUST`** — Per-subreddit credibility multiplier applied before collapsing to a per-ticker row:

   | Subreddit | Trust Weight |
   |-----------|-------------|
   | r/investing | 1.5 |
   | r/stocks | 1.2 |
   | r/stockmarket | 1.0 |
   | r/wallstreetbets | 0.7 |

### Divergence Signal

```
divergence = 1  when  sentiment_momentum > 0  AND  price_momentum < 0
```

Rolling metrics use a 6-run window (~2 days at 3 runs/day). `price_momentum` uses Yahoo's `pct_change` (normalized daily % change) rather than raw price diffs, making signals cross-ticker comparable regardless of price scale.

`volume_momentum` provides a third dimension: surging volume during a divergence event strengthens the signal.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Scraping | Playwright (headless Chromium) |
| HTTP / Reddit | requests |
| NLP | NLTK VADER |
| Validation | Pydantic v2 |
| Data | pandas, PyArrow, parquet |
| Visualization | Streamlit, Plotly |
| Orchestration | GitHub Actions |
| Storage | Git (append-only parquet as database) |

---

## Project Structure

```
market-cynic-pipeline/
├── main.py                          # Pipeline orchestrator (gatekeeper pattern)
├── src/
│   ├── ingestion/
│   │   ├── yahoo_probe.py           # Bronze: Playwright Yahoo Finance scraper
│   │   └── reddit_sentinel.py       # Bronze: Multi-subreddit Reddit sentiment
│   ├── transformation/
│   │   ├── cleaner.py               # Silver: Pydantic validation + cleaning
│   │   └── aggregator.py            # Gold: Sentiment merge + divergence metrics
│   ├── utils/
│   │   ├── schemas.py               # StockSchema (Pydantic) + signal_weight
│   │   └── logger.py                # Shared logger setup
│   └── visualization/
│       └── dashboard.py             # Streamlit dashboard
├── data/
│   └── market_history.parquet       # Append-only historical record (git as DB)
├── .github/workflows/
│   └── schedule.yml                 # GitHub Actions: 3x daily automated runs
└── explore.ipynb                    # Jupyter notebook for data exploration
```

---

## Running Locally

```bash
# Install dependencies
pip install -r requirements.txt
python -m playwright install chromium --with-deps

# Run the full pipeline (must use -m flag for absolute imports)
python -m main

# Launch the dashboard
streamlit run src/visualization/dashboard.py
```

> **WSL note:** The `.venv` is a Windows venv created with `uv`. Invoke it directly via `.venv/Scripts/python.exe -m main`.

---

## Dashboard

The Streamlit dashboard provides:

- **KPI metrics** — price, daily % change, cynic sentiment score, Reddit mentions, volume
- **Price vs. Sentiment chart** — dual-axis time series with divergence points highlighted in amber
- **Momentum indicators** — sentiment momentum and price momentum overlaid
- **The Verdict** — live divergence detection with volume confirmation
- **Echo Chamber Alert** — fires when sentiment volatility is extremely low (consensus forming)
- **Historical divergence table** — every flagged signal across all tickers and runs

---

## Deployment

GitHub Actions runs the pipeline three times daily on a clean Ubuntu environment:

| Run | UTC | ET | Purpose |
|-----|-----|----|---------|
| Pre-market | 9:00 AM | 5:00 AM | Baseline before open |
| Mid-session | 3:00 PM | 11:00 AM | Active trading sentiment |
| Post-close | 9:30 PM | 5:30 PM | Reaction after close |

On each run: installs dependencies (pip-cached), runs `python -m main`, uploads logs as artifacts (7-day retention), and commits the updated `market_history.parquet` back to master via `MarketCynicBot`.

---

## Key Design Decisions

**Git as a database** — `market_history.parquet` is append-only and committed directly to the repo on every run. Simple, zero infrastructure, full version history on the data itself.

**Gatekeeper pattern** — `main.py` checks file existence and content after each stage. If ingestion returns no data or the Gold layer fails to write, the pipeline exits with a non-zero code rather than silently propagating bad data downstream.

**Inner join at Gold** — Only tickers that appear in *both* Yahoo Finance and Reddit data make it to the Gold layer. A stock with no Reddit discussion has no sentiment signal and no place in the output.

**Subreddit trust weighting** — Rather than treating all Reddit sources equally, the pipeline discounts speculative communities before aggregating. A YOLO post on WSB carries less weight than a fundamental analysis post on r/investing.
