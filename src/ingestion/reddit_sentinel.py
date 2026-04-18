import time
import requests
import re
import nltk # type:ignore
from nltk.sentiment.vader import SentimentIntensityAnalyzer # type:ignore
from src.utils.schemas import StockSchema

nltk.download("vader_lexicon", quiet=True)

from src.utils.logger import setup_logger
logger = setup_logger("RedditSentinel")

# Includes r/stocks, r/wallstreetbets, r/investing, and r/stockmarket
SUBREDDIT_CONFIGS = [
    {
        "name": "stocks",
        "url": "https://www.reddit.com/r/stocks/hot.json?limit=100",
        "flair_blocklist": [],
    },
    {
        "name": "wallstreetbets",
        "url": "https://www.reddit.com/r/wallstreetbets/hot.json?limit=100",
        "flair_blocklist": ["Meme", "YOLO", "Gain", "Loss"],
    },
    {
        "name": "investing",
        "url": "https://www.reddit.com/r/investing/hot.json?limit=100",
        "flair_blocklist": [],
    },
    {
        "name": "stockmarket",
        "url": "https://www.reddit.com/r/stockmarket/hot.json?limit=100",
        "flair_blocklist": ["Newbie"],
    },
]

def get_reddit_data(symbol_list, current_prices):
    headers = {"User-Agent": "MarketCynicPipeline/0.1 by DeanKuhn"}
    sia = SentimentIntensityAnalyzer()
    collected_data = []
    seen_post_ids = set()

    # Loop through subreddits, copying the name, url, and any flairs to ignore
    for config in SUBREDDIT_CONFIGS:
        name = config["name"]
        url = config["url"]
        flair_blocklist = config["flair_blocklist"]

        logger.info(f"Scanning r/{name} for {symbol_list}...")

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            posts = response.json()["data"]["children"]

            for post in posts:
                p_data = post["data"]

                # Skip automoderator posts
                if p_data.get("author") == "AutoModerator":
                    continue
                # Skip stickied posts
                if p_data.get("stickied") == True:
                    continue
                # Skip removed posts
                if p_data.get("removed_by_category") is not None:
                    continue

                # Block posts with flairs that will mislead results
                flair = p_data.get("link_flair_text")
                if flair in flair_blocklist:
                    continue

                # Check for duplicates and reposts by saving post id
                post_id = p_data.get("id")
                if post_id in seen_post_ids:
                    continue
                seen_post_ids.add(post_id)

                title = p_data.get("title", "")
                body = p_data.get("selftext", "")

                # Ignore removed or deleted posts, keep the title though
                if body in ("[removed]", "[deleted]"):
                    body = ""
                full_text = (title + " " + body).upper()

                # Loop through each symbol
                for symbol in symbol_list:
                    pattern = rf"\b{symbol.upper()}\b"

                    # If re.search pulls nothing, simply skip the stock
                    if re.search(pattern, full_text):
                        sentiment_score = sia.polarity_scores(
                            title + " " + body)["compound"]

                        try:
                            # Also, skip if for some reason price was missed
                            price = current_prices.get(symbol)
                            if price is None:
                                logger.warning(
                                    f"No price found for {symbol}, skipping.")
                                continue

                            # Fit everything to the schema layout
                            stock_entry = StockSchema(
                                symbol=symbol,
                                price=price,
                                post_id=post_id,
                                flair=flair,
                                subreddit=name,
                                ups=int(p_data.get("ups", 0)),
                                upvote_ratio=float(p_data.get(
                                    "upvote_ratio", 1.0)),

                                num_comments=int(p_data.get(
                                    "num_comments", 0)),

                                is_original_content=bool(p_data.get(
                                    "is_original_content", False)),

                                timestamp=p_data.get("created_utc"),
                                sentiment_score=sentiment_score
                            )

                            collected_data.append(stock_entry)

                        # Log failed symbol validations
                        except Exception as ve:
                            logger.warning(
                                f"Validation failed for {symbol}: {ve}")

        except Exception as e:
            logger.error(f"Failed to fetch r/{name}: {e}", exc_info=True)

        # Don't overload Reddit's API
        time.sleep(1)

    return collected_data

# Main function below for testing
if __name__ == "__main__":
    test_symbols = ["NVDA", "IONQ", "QBTS", "TSLA", "HIMS"]
    current_prices = \
        {"NVDA": 100, "IONQ": 100, "QBTS": 100, "TSLA": 100, "HIMS": 100}
    results = get_reddit_data(test_symbols, current_prices)
    for r in results:
        logger.info(f"[{r.subreddit}] {r.symbol} | flair={r.flair} | "\
                    f"sentiment={r.sentiment_score} | post_id={r.post_id}")