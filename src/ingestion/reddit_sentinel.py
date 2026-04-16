import requests
import time
import re
import nltk # type:ignore
from nltk.sentiment.vader import SentimentIntensityAnalyzer # type:ignore

nltk.download("vader_lexicon", quiet=True)

def get_reddit_data(symbol_list):
    # Define user agent; Reddit requires one so they know it's not a bot
    headers = {"User-Agent": "MargetCynicPipeline/0.1 by DeanKuhn"}

    sia = SentimentIntensityAnalyzer()

    # Target the "hot" posts of these subreddits
    url = "https://www.reddit.com/r/stocks/hot.json?limit=100"
    stats = {symbol: {"count": 0, "sentiment": 0.0} for symbol in symbol_list}
    print(f"Bypassing API... Scanning Reddit JSON for {symbol_list}...")

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        posts = data["data"]["children"]

        for post in posts:
            title = post["data"]["title"]
            body = post["data"]["selftext"]
            full_text = (title + " " + body).upper()

            for symbol in symbol_list:
                pattern = rf"\b{symbol.upper()}\b"
                if re.search(pattern, full_text):
                    # Get sentiment of the post
                    score = sia.polarity_scores(title + " " + body)["compound"]
                    stats[symbol]["count"] += 1
                    stats[symbol]["sentiment"] += score

        for symbol in stats:
            if stats[symbol]["count"] > 0:
                stats[symbol]["sentiment"] /= stats[symbol]["count"]

        return stats
    except Exception as e:
        print(f"Reddit Bypass Failed: {e}")
        return stats

if __name__ == "__main__":
    test_symbols = ["NVDA", "IONQ", "QBTS", "TSLA", "HIMS"]
    print(get_reddit_data(test_symbols))