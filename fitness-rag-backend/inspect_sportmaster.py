from playwright.sync_api import sync_playwright
import re

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    
    print("Opening Sportmaster locations...")
    page.goto("https://sportmaster.mk/locations")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(3000)
    
    # Scroll to load content
    page.mouse.wheel(0, 5000)
    page.wait_for_timeout(2000)
    
    html = page.content()
    
    # Save HTML for inspection
    with open("sportmaster_page.html", "w", encoding="utf-8") as f:
        f.write(html)
    
    print("✅ HTML saved to sportmaster_page.html")
    
    # Try to find gym cards/items
    print("\n=== Looking for gym data ===\n")
    
    # Look for common patterns
    patterns = [
        r'<div[^>]*class="[^"]*location[^"]*"[^>]*>.*?</div>',
        r'<div[^>]*data-gym[^>]*>.*?</div>',
        r'<card[^>]*>.*?</card>',
    ]
    
    # Print relevant sections
    if "gym" in html.lower():
        print("Found 'gym' references in HTML")
    
    # Get all text content
    text_content = page.evaluate("document.body.innerText")
    print("Page text (first 2000 chars):")
    print(text_content[:2000])
    
    # Look for location elements
    locations = page.query_selector_all("[data-location], .location, .gym-card, .location-card")
    print(f"\n✅ Found {len(locations)} location elements")
    
    # Try to get all h2, h3 headings (likely gym names)
    headings = page.query_selector_all("h2, h3")
    print(f"\n=== Headings found: {len(headings)} ===")
    for i, h in enumerate(headings[:5]):
        print(f"{i}: {h.inner_text()}")
    
    browser.close()

