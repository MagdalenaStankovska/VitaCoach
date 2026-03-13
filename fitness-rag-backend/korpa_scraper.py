from playwright.sync_api import sync_playwright
import json


URL = "https://korpa.mk/partner/junk-food"


def scrape_korpa():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # open browser so you can see it
        page = browser.new_page()

        print("Opening Korpa...")
        page.goto(URL)

        # wait for menu items to load
        page.wait_for_timeout(5000)

        dishes = []

        # find dish cards
        items = page.query_selector_all("h6")

        for item in items:
            name = item.inner_text()

            dish = {
                "name": name
            }

            dishes.append(dish)

        browser.close()

        return dishes


if __name__ == "__main__":
    data = scrape_korpa()

    with open("korpa_dishes.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    print(f"Scraped {len(data)} dishes!")