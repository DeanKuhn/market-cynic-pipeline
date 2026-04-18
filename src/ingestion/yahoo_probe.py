import json
import asyncio
from playwright.async_api import async_playwright # type:ignore

from src.utils.logger import setup_logger
logger = setup_logger("YahooScraper")

# Async functions mean that the computer will wait while doing longer tasks
# (such as loading a webpage), allowing other processes to run concurrently
async def run_probe(output_file: str):
    # Define an asynchronous function using playwright
    async with async_playwright() as p:
        # Launch a headless browser with p as playwright
        browser = await p.chromium.launch(headless=True)

        # Define who the broswer sees as visiting
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win 64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
        )

        # Wait for a new tab to open, and then visit Yahoo Finance most active
        page = await context.new_page()
        url = "https://finance.yahoo.com/markets/stocks/most-active/"
        logger.info(f"Attempting to reach: {url}")

        try:
            # "domcontentloaded" waits for certain things but not others, such
            # as ads that may take too long to load
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            logger.info("Waiting for data table to load...")

            # Wait for the table we are looking for to show up
            await page.wait_for_selector(
                '[data-testid="data-table-v2-row"]', timeout=15000
            )

            # The rows we are looking for have a unique data-testid
            rows = await page.query_selector_all(
                '[data-testid="data-table-v2-row"]'
            )

            stock_data = []

            # Check out the top 10 rows (using the unique cell names instead
            # of indices, as the former is more reliable)
            for row in rows[:10]:
                try:
                    symbol_el  = await row.query_selector(
                        '[data-testid-cell="ticker"]')

                    name_el    = await row.query_selector(
                        '[data-testid-cell="companyshortname.raw"]')

                    price_el   = await row.query_selector(
                        '[data-testid-cell="intradayprice"]')

                    volume_el  = await row.query_selector(
                        '[data-testid-cell="dayvolume"]')

                    pct_chg_el = await row.query_selector(
                        '[data-testid-cell="percentchange"]')

                    # Skip row if any critical field is missing
                    if not all([symbol_el, name_el, price_el]):
                        logger.warning("Skipping row: missing critical field(s).")
                        continue

                    # Strip data to clean it before sending to reddit_sentinel
                    symbol  = (await symbol_el.inner_text()).strip()
                    name    = (await name_el.inner_text()).strip()
                    price   = (await price_el.inner_text()).strip()
                    volume  = (await volume_el.inner_text()).strip() \
                        if volume_el else None
                    pct_chg = (await pct_chg_el.inner_text()).strip() \
                        if pct_chg_el else None

                    # Append data to dictionary
                    stock_data.append({
                        "symbol": symbol,
                        "name": name,
                        "price": price,
                        "volume": volume,
                        "pct_change": pct_chg
                    })

                except Exception as row_e:
                    logger.warning(f"Skipping malformed row: {row_e}")
                    continue

            for stock in stock_data:
                logger.info(f"Captured: {stock['symbol']} - {stock['price']}")

            # Scraper-level check (warn, but let main.py decide to terminate)
            if not stock_data:
                logger.warning(
                    "Scraper captured 0 records. "
                    "Table may have failed to render or structure has changed."
                )

            # Dump data into a .json file for cleaning
            with open(output_file, "w") as f:
                json.dump(stock_data, f, indent=4)

        # Take a picture if any error states come up with visiting the page
        except Exception as e:
            await page.screenshot(path="error_state.png")
            logger.error(f"Navigation failed: {e}", exc_info=True)
            with open(output_file, "w") as f:
                json.dump([], f)

        # Close the browser so that we don't leave it stranded in RAM
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(run_probe("data/raw_stocks.json"))