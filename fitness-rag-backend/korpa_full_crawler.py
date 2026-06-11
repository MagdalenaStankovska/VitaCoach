from playwright.sync_api import sync_playwright
import json
import time
import requests
import random

BASE_URL = "https://korpa.mk"
API_KEY = "0J9ASLD2Lk7evnRUh8SZel6nes69xGSf5ehyh6fe"


# -----------------------------
# NUTRITION LOOKUP
# -----------------------------
def get_nutrition(food_name):

    if API_KEY == "":
        return None

    url = "https://api.nal.usda.gov/fdc/v1/foods/search"

    params = {
        "query": food_name,
        "api_key": API_KEY,
        "pageSize": 1
    }

    try:
        response = requests.get(url, params=params)
        data = response.json()

        if "foods" not in data or len(data["foods"]) == 0:
            return None

        food = data["foods"][0]

        calories = None
        protein = None

        for nutrient in food.get("foodNutrients", []):

            if nutrient["nutrientName"] == "Energy":
                calories = nutrient["value"]

            if nutrient["nutrientName"] == "Protein":
                protein = nutrient["value"]

        return {"calories": calories, "protein": protein}

    except:
        return None


# -----------------------------
# GET RESTAURANTS
# -----------------------------
def get_restaurants(page):

    print("Opening Korpa homepage...")

    page.goto(BASE_URL)

    # wait so user can solve verification
    print("Solve verification if it appears...")
    time.sleep(20)

    page.wait_for_timeout(5000)

    # scroll to load restaurants
    for _ in range(8):
        page.mouse.wheel(0, 5000)
        page.wait_for_timeout(1500)

    links = page.query_selector_all("a")

    restaurants = set()

    for link in links:

        href = link.get_attribute("href")

        if href and href.startswith("/partner/"):

            restaurants.add(BASE_URL + href)

    restaurants = list(restaurants)

    print("Found restaurants:", len(restaurants))

    return restaurants


# -----------------------------
# SCRAPE RESTAURANT
# -----------------------------
def scrape_restaurant(page, url):

    print("Scraping:", url)

    for attempt in range(3):

        try:

            page.goto(url)

            page.wait_for_selector("h6", timeout=12000)

            break

        except:

            print("Retrying...", url)
            time.sleep(5)

    items = page.query_selector_all("h6")

    if len(items) == 0:
        print("⚠️ Blocked or no menu:", url)
        return []

    dishes = []

    print("Dishes found:", len(items))

    for item in items:

        name = item.inner_text().strip()

        nutrition = get_nutrition(name)

        dish = {
            "restaurant": url.split("/")[-1],
            "dish": name,
            "calories": nutrition["calories"] if nutrition else None,
            "protein": nutrition["protein"] if nutrition else None
        }

        dishes.append(dish)

        time.sleep(random.uniform(0.5, 1.5))

    return dishes


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

        all_dishes = []

        for i, restaurant in enumerate(restaurants):

            try:

                dishes = scrape_restaurant(page, restaurant)

                all_dishes.extend(dishes)

                time.sleep(random.uniform(3, 5))

                # cooldown every 15 restaurants
                if i % 15 == 0 and i != 0:

                    print("Cooling down to avoid Cloudflare...")
                    time.sleep(60)

            except Exception as e:

                print("Error:", e)

        context.close()

        return all_dishes


# -----------------------------
# MAIN
# -----------------------------
if __name__ == "__main__":

    dataset = run_scraper()

    with open("foods_dataset.json", "w", encoding="utf-8") as f:

        json.dump(dataset, f, indent=4, ensure_ascii=False)

    print("Saved", len(dataset), "dishes")