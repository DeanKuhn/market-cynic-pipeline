import requests
import re
from datetime import datetime
import nltk # type:ignore
from nltk.sentiment.vader import SentimentIntensityAnalyzer # type:ignore
from src.utils.schemas import StockSchema

nltk.download("vader_lexicon", quiet=True)

from src.utils.logger import setup_logger
logger = setup_logger("RedditSentinel")

def get_reddit_data(symbol_list, current_prices):
    # current_prices is a dict { "NVDA": 900.0 } passed from price scraper

    # Define user agent; Reddit requires one so they know it's not a bot
    headers = {"User-Agent": "MargetCynicPipeline/0.1 by DeanKuhn"}
    sia = SentimentIntensityAnalyzer()

    # Target the "hot" posts of these subreddits
    url = "https://www.reddit.com/r/stocks/hot.json?limit=100"

    # return a list of StockSchema objects
    collected_data = []
    logger.info(f"Scanning Reddit JSON for {symbol_list}...")

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        posts = data["data"]["children"]

        for post in posts:
            p_data = post["data"]
            title = p_data["title"]
            body = p_data["selftext"]
            full_text = (title + " " + body).upper()

            for symbol in symbol_list:
                pattern = rf"\b{symbol.upper()}\b"
                if re.search(pattern, full_text):
                    # 1. Perform Sentiment Analysis
                    sentiment_score = sia.polarity_scores(title + " " + body)["compound"]

                    # 2. Map JSON to StockSchema
                    try:
                        stock_entry = StockSchema(
                            symbol=symbol,
                            price=current_prices.get(symbol, 0.0),
                            name=str(p_data.get("title", ""))[:50],
                            ups=int(p_data.get("ups", 0)),
                            upvote_ratio=float(p_data.get("upvote_ratio", 1.0)),
                            num_comments=int(p_data.get("num_comments", 0)),
                            is_original_content=bool(p_data.get("is_original_content", False)),
                            # Convert Unix float to datetime so the Schema doesn't get confused
                            timestamp=datetime.fromtimestamp(p_data.get("created_utc", datetime.now().timestamp())),
                            sentiment_score=sentiment_score # Ensure this matches your Schema field name
                        )
                        collected_data.append(stock_entry)
                    except Exception as ve:
                        logger.warning(f"Validation failed for {symbol}: {ve}")
        return collected_data
    except Exception as e:
        logger.error(f"Reddit Scrape Failed: {e}", exc_info=True)
        return collected_data

# main function below for testing
if __name__ == "__main__":
    test_symbols = ["NVDA", "IONQ", "QBTS", "TSLA", "HIMS"]
    logger.info(get_reddit_data(test_symbols))