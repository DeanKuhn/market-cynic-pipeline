import asyncio
from playwright.async_api import async_playwright # type:ignore

async def run_probe(output_file: str):
    async with async_playwright() as p:
        # launch the browser in 'headless' mode
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win 64; x64) " \
                "AppleWebKit/537.36 (KHTML, like Gecko) " \
                    "Chrome/121.0.0.0 Safari/537.36"
        )

        page = await context.new_page()
        url = "https://finance.yahoo.com/markets/stocks/most-active/"
        print(f"Attempting to reach: {url}")
        try:
            # navigate and wait for the network to be 'idle' (JS fully loaded)
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)

            # wait for the table we are looking for to exist
            print("Waiting for data table to load...")
            await page.wait_for_selector("table", timeout=15000)

            rows = await page.query_selector_all("tbody tr")

            stock_data = []

            for row in rows[:10]:
                cells = await row.query_selector_all("td")
                if len(cells) >= 3:
                    symbol = await cells[0].inner_text()
                    name = await cells[1].inner_text()
                    price = await cells[3].inner_text()

                    stock_data.append({
                        "symbol": symbol.strip(),
                        "name": name.strip(),
                        "price": price.strip()
                    })

            # print results
            for stock in stock_data:
                print(f"Captured: {stock['symbol']} - {stock['price']}")

            import json
            with open(output_file, "w") as f:
                json.dump(stock_data, f, indent=4)

        except Exception as e:
            await page.screenshot(path="error_state.png")
            print(f"Navigation failed: {e}")

        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(run_probe())