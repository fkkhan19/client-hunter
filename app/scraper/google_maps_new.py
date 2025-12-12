# client_hunter/app/scraper/google_maps_new.py
import os, sys
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import time
from playwright.sync_api import sync_playwright
import requests

FREE_HOSTS = ["wix", "wordpress", "blogspot", "weebly", "site123", "webnode", "squarespace", "tumblr"]
BROKEN_SIGNS = ["under construction", "coming soon", "maintenance", "domain parked", "page not found", "404"]


def is_free_host(url):
    if not url:
        return False
    u = url.lower()
    return any(h in u for h in FREE_HOSTS)


def is_broken(url):
    if not url:
        return True
    try:
        if not url.startswith("http"):
            url = "http://" + url
        r = requests.get(url, timeout=7)
        if r.status_code != 200:
            return True
        return any(sig in r.text.lower() for sig in BROKEN_SIGNS)
    except:
        return True


def get_map_results(category, city, max_results=30):
    """
    RETURNS A LIST OF DICTS:
    {
       "name": str,
       "category": str,
       "location": str,
       "contact": str | None,
       "website": str | None,
       "score": int
    }
    """
    query = f"{category} in {city}"
    print(f"\n🗺️ PLAYWRIGHT SCRAPER: Searching '{query}'")

    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # set False for visible browser
        page = browser.new_page()

        url = f"https://www.google.com/maps/search/{query.replace(' ', '+')}"
        page.goto(url, timeout=60000)

        # scroll to load more results
        for _ in range(15):
            page.mouse.wheel(0, 2500)
            time.sleep(0.6)

        items = page.locator("div[role='article']")
        count = items.count()
        print(f"📌 Found {count} raw places")

        for i in range(min(count, max_results)):
            try:
                entry = items.nth(i)
                name = entry.locator("h3").inner_text(timeout=2000)

                entry.click(timeout=3000)
                time.sleep(1.1)

                website = None
                phone = None
                address = None

                if page.locator("a[data-item-id='authority']").count() > 0:
                    website = page.locator("a[data-item-id='authority']").first.get_attribute("href")

                if page.locator("button[data-item-id*='phone']").count() > 0:
                    phone = page.locator("button[data-item-id*='phone']").first.inner_text().strip()

                if page.locator("button[data-item-id='address']").count() > 0:
                    address = page.locator("button[data-item-id='address']").first.inner_text().strip()

                if not address:
                    address = city

                # scoring logic
                if not website:
                    score = 100
                elif is_free_host(website):
                    score = 90
                elif is_broken(website):
                    score = 95
                else:
                    print(f"❌ Reject (good website): {name}")
                    continue

                results.append({
                    "name": name,
                    "category": category,
                    "location": address,
                    "contact": phone,
                    "website": website,
                    "score": score
                })

            except Exception as e:
                print(f"⚠️ Error reading item {i}: {e}")
                continue

        browser.close()

    print(f"✅ DONE — Returning {len(results)} scraped leads\n")
    return results
