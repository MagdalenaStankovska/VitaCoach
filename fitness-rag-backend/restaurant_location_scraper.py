from playwright.sync_api import sync_playwright
import json
import time
import random

BASE_URL = "https://korpa.mk"

# -----------------------------
# GET RESTAURANTS
# -----------------------------
def get_restaurants(page):
    print("Opening Korpa homepage...")
    page.goto(BASE_URL)

    print("Solve verification if needed...")
    input("👉 Press ENTER after solving Cloudflare...")

    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(3000)

    # scroll to load all restaurants
    for _ in range(15):
        page.mouse.wheel(0, 5000)
        page.wait_for_timeout(1500)

    links = page.locator("a[href^='/partner/']").all()
    restaurants = set()

    for link in links:
        try:
            href = link.get_attribute("href")
            if href:
                restaurants.add(BASE_URL + href)
        except:
            continue

    restaurants = list(restaurants)
    print("✅ Found restaurants:", len(restaurants))
    return restaurants

# -----------------------------
# EXTRACT ADDRESS AND COORDINATES FROM MAP LINK
# -----------------------------
def extract_map_data(page):
    try:
        links = page.query_selector_all("a[href*='google.com/maps']")
        for link in links:
            href = link.get_attribute("href")
            if not href:
                continue

            lat, lng, address = None, None, None

            # Extract coordinates from ll=
            if "ll=" in href:
                coords = href.split("ll=")[1].split("&")[0]
                lat, lng = coords.split(",")
                lat, lng = float(lat), float(lng)

            # Extract address from q=
            if "q=" in href:
                address = href.split("q=")[1].split("&")[0]
                address = address.replace("+", " ")

            if lat is not None and lng is not None:
                return address, lat, lng

    except Exception as e:
        print("❌ Map extraction error:", e)

    return None, None, None

# -----------------------------
# SCRAPE SINGLE RESTAURANT
# -----------------------------
def scrape_restaurant_info(page, url):

    print("\n🔎 Scraping:", url)

    # load page
    for attempt in range(3):
        try:
            page.goto(url)
            page.wait_for_load_state("networkidle")
            break
        except:
            print("Retrying...")
            time.sleep(5)

    # NAME
    try:
        name = page.locator("h1").first.inner_text().strip()
    except:
        name = url.split("/")[-1]

    # 🔥 CLICK LOCATION (IMPORTANT)
    try:
        page.locator("text=Skopje").first.click()
        page.wait_for_timeout(2000)
    except:
        print("❌ Could not click location")

    # 🔥 EXTRACT ADDRESS FROM POPUP
    address = None
    try:
        texts = page.locator("text=North Macedonia").all()
        for t in texts:
            txt = t.inner_text().strip()
            if len(txt) > 10:
                address = txt
                break
    except:
        pass

    # 🔥 EXTRACT MAP COORDS FROM IFRAME
    lat, lng = None, None
    try:
        iframe = page.query_selector("iframe[src*='google.com/maps']")
        if iframe:
            src = iframe.get_attribute("src")

            print("🌐 MAP SRC:", src)

            if "ll=" in src:
                coords = src.split("ll=")[1].split("&")[0]
                lat, lng = coords.split(",")
                lat, lng = float(lat), float(lng)
    except Exception as e:
        print("❌ iframe error:", e)

    # CLOSE POPUP
    try:
        page.keyboard.press("Escape")
    except:
        pass

    print("➡️ NAME:", name)
    print("➡️ ADDRESS:", address)
    print("➡️ LAT:", lat)
    print("➡️ LNG:", lng)

    return {
        "name": name,
        "url": url,
        "address": address,
        "latitude": lat,
        "longitude": lng
    }

# -----------------------------
# RUN SCRAPER
# -----------------------------
def run_scraper():
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir="korpa_profile",
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = context.new_page()

        restaurants = get_restaurants(page)
        results = []

        for i, restaurant in enumerate(restaurants):
            try:
                data = scrape_restaurant_info(page, restaurant)
                if data:
                    results.append(data)

                time.sleep(random.uniform(2, 4))

                if i % 15 == 0 and i != 0:
                    print("\n❄️ Cooling down...\n")
                    time.sleep(60)

            except Exception as e:
                print("Error:", e)

        context.close()
        return results

# -----------------------------
# MAIN
# -----------------------------
if __name__ == "__main__":
    dataset = run_scraper()

    with open("restaurants_dataset.json", "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=4, ensure_ascii=False)

    print("\n✅ Saved", len(dataset), "restaurants")