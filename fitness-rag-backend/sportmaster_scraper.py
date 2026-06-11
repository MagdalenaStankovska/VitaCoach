from playwright.sync_api import sync_playwright
import json
import time
import random
from urllib.parse import quote
import sys

# Fix for encoding issues on Windows
sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "https://sportmaster.mk"
LOCATIONS_URL = "https://sportmaster.mk/locations"

# =============================
# GET ALL GYM LOCATIONS
# =============================
def get_gym_locations(page):
    print("Opening Sportmaster locations page...")
    page.goto(LOCATIONS_URL)
    
    print("Waiting for page to load...")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(3000)
    
    # Scroll to load all gyms
    for _ in range(10):
        page.mouse.wheel(0, 5000)
        page.wait_for_timeout(1500)
    
    # Get all gym location cards/links
    # Adjust selector based on actual HTML structure
    gym_links = []
    
    try:
        # Try multiple selectors
        selectors = [
            "a[href*='/locations/']",
            ".location-card a",
            "[data-gym-link]",
            "a.gym-link"
        ]
        
        for selector in selectors:
            try:
                elements = page.locator(selector).all()
                if elements:
                    print(f"✓ Found elements with selector: {selector}")
                    for elem in elements:
                        href = elem.get_attribute("href")
                        if href and ("/location" in href or "/gym/" in href):
                            if href.startswith("http"):
                                full_url = href
                            else:
                                # Ensure proper URL construction with /
                                if not href.startswith("/"):
                                    href = "/" + href
                                full_url = BASE_URL + href
                            gym_links.append(full_url)
                    break
            except:
                continue
    except Exception as e:
        print(f"Error finding gym links: {e}")
    
    # Remove duplicates
    gym_links = list(set(gym_links))
    print(f"✅ Found gym locations: {len(gym_links)}")
    
    if not gym_links:
        print("⚠️ No gym links found, trying alternative method...")
        # Get all links from page
        all_links = page.locator("a").all()
        for link in all_links:
            href = link.get_attribute("href")
            if href and ("location" in href.lower() or "gym" in href.lower()):
                if href.startswith("http"):
                    full_url = href
                else:
                    if not href.startswith("/"):
                        href = "/" + href
                    full_url = BASE_URL + href
                if full_url not in gym_links and full_url != LOCATIONS_URL:
                    gym_links.append(full_url)
    
    return gym_links

# =============================
# EXTRACT COORDINATES FROM MAP
# =============================
def extract_coordinates_from_maps(url):
    """Extract lat/lng from Google Maps URL"""
    try:
        if "ll=" in url:
            coords = url.split("ll=")[1].split("&")[0]
            lat, lng = coords.split(",")
            return float(lat), float(lng)
    except:
        pass
    return None, None

# =============================
# SCRAPE SINGLE GYM
# =============================
def scrape_gym_info(page, url):
    print(f"\n🏋️ Scraping gym: {url}")
    
    try:
        page.goto(url, timeout=30000)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)
    except Exception as e:
        print(f"❌ Failed to load page: {e}")
        return None
    
    # Get gym name
    name = None
    try:
        # Try common heading selectors
        selectors = ["h1", ".gym-name", "[data-gym-name]", ".title"]
        for selector in selectors:
            try:
                elem = page.locator(selector).first
                if elem:
                    name = elem.inner_text().strip()
                    if name:
                        break
            except:
                continue
    except:
        name = url.split("/")[-1].replace("-", " ").title()
    
    # Get address
    address = None
    try:
        selectors = [
            "text=North Macedonia",
            ".address",
            "[data-address]",
            ".location-address"
        ]
        for selector in selectors:
            try:
                elem = page.locator(selector).first
                if elem:
                    address = elem.inner_text().strip()
                    if address and len(address) > 5:
                        break
            except:
                continue
    except:
        pass
    
    # Get gym categories
    categories = []
    try:
        # Look for badge elements with class badge_category
        category_elements = page.query_selector_all(".badge_category, [class*='category'], .label-container label")
        for elem in category_elements:
            try:
                cat_text = elem.inner_text().strip()
                if cat_text and len(cat_text) > 0 and cat_text not in categories:
                    categories.append(cat_text)
            except:
                continue
    except Exception as e:
        print(f"⚠️ Error extracting categories: {e}")
    
    # Try to extract coordinates from map or link
    latitude = None
    longitude = None
    
    try:
        # Look for Google Maps iframe
        iframe = page.query_selector("iframe[src*='google.com/maps']")
        if iframe:
            src = iframe.get_attribute("src")
            print(f"🗺️ Found maps iframe: {src}")
            latitude, longitude = extract_coordinates_from_maps(src)
        
        # Try to find map link
        if not latitude:
            map_links = page.query_selector_all("a[href*='google.com/maps']")
            for link in map_links:
                href = link.get_attribute("href")
                if href:
                    print(f"🗺️ Found maps link: {href}")
                    latitude, longitude = extract_coordinates_from_maps(href)
                    if latitude:
                        break
    except Exception as e:
        print(f"❌ Error extracting coordinates: {e}")
    
    # Try clicking on address/location to open map
    if not latitude:
        try:
            print("⏳ Trying to click location element...")
            selectors = [
                "a[href*='google.com/maps']",
                ".map-link",
                "[data-map]",
                "text=View on map"
            ]
            for selector in selectors:
                try:
                    elem = page.locator(selector).first
                    if elem:
                        page.evaluate("arguments[0].scrollIntoView();", elem.element_handle())
                        elem.click()
                        page.wait_for_timeout(2000)
                        
                        # Try extracting from opened popup/iframe
                        iframe = page.query_selector("iframe[src*='google.com/maps']")
                        if iframe:
                            src = iframe.get_attribute("src")
                            latitude, longitude = extract_coordinates_from_maps(src)
                            if latitude:
                                break
                except:
                    continue
        except Exception as e:
            print(f"⚠️ Could not click location: {e}")
    
    print(f"✅ Name: {name}")
    print(f"✅ Address: {address}")
    print(f"✅ Categories: {', '.join(categories) if categories else 'None'}")
    print(f"✅ Coordinates: {latitude}, {longitude}")
    
    return {
        "name": name,
        "url": url,
        "address": address,
        "category": ", ".join(categories) if categories else None,
        "categories": categories if categories else [],
        "latitude": latitude,
        "longitude": longitude
    }

# =============================
# RUN SCRAPER
# =============================
def run_scraper():
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir="sportmaster_profile",
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = context.new_page()
        
        gym_links = get_gym_locations(page)
        results = []
        
        if not gym_links:
            print("❌ No gym links found. Check if the website structure has changed.")
            context.close()
            return results
        
        for i, gym_url in enumerate(gym_links):
            try:
                data = scrape_gym_info(page, gym_url)
                if data and data.get("name"):
                    results.append(data)
                
                time.sleep(random.uniform(2, 4))
                
                if i % 10 == 0 and i != 0:
                    print("\n❄️ Cooling down to avoid blocking...\n")
                    time.sleep(30)
            
            except Exception as e:
                print(f"❌ Error scraping gym: {e}")
        
        context.close()
        return results

# =============================
# MAIN
# =============================
if __name__ == "__main__":
    print("🏋️ Starting Sportmaster Gym Scraper...")
    print(f"Target: {LOCATIONS_URL}\n")
    
    dataset = run_scraper()
    
    if dataset:
        with open("gyms_dataset.json", "w", encoding="utf-8") as f:
            json.dump(dataset, f, indent=4, ensure_ascii=False)
        
        print(f"\n✅ Successfully scraped {len(dataset)} gyms")
        print(f"📁 Saved to gyms_dataset.json")
        
        # Print summary
        with_coords = [g for g in dataset if g.get("latitude") and g.get("longitude")]
        print(f"📍 Gyms with coordinates: {len(with_coords)}/{len(dataset)}")
    else:
        print("\n❌ No gyms scraped. The website structure may have changed.")






