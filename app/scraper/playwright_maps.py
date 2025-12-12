# client_hunter/app/scraper/playwright_maps.py
"""
Playwright-based Google Maps scraper (headless, server-ready).

Usage:
    from app.scraper.playwright_maps import get_map_results
    results = get_map_results("mobile repair", "Pune", max_results=50)

Return:
    list of dicts:
    {
      "name": str,
      "category": str,
      "location": str,
      "contact": str | None,
      "website": str | None,
      "score": int
    }

Notes:
- Requires Playwright Python package and browser binaries installed.
- Works headless on Linux servers with the required system deps.
- Optional proxy support: set PLAYWRIGHT_PROXY env var to "http://user:pass@host:port"
- Respect Google TOS and scale politely (use proxy/rotation for production).
"""

import os
import re
import time
import json
import traceback
import asyncio
from urllib.parse import quote_plus, urlparse

# Playwright imports (installed separately)
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

# DB model only used for dedupe/compat in scheduler; this scraper returns dicts
# from app.models import Lead  # not needed here

# Config
DEFAULT_WAIT = int(os.getenv("PLAYWRIGHT_WAIT_MS", 3000)) / 1000.0  # seconds
DELAY_BETWEEN_ITEMS = float(os.getenv("PLAYWRIGHT_ITEM_DELAY", 1.0))
HEADLESS = os.getenv("PLAYWRIGHT_HEADLESS", "1") not in ("0", "false", "False")
PROXY = os.getenv("PLAYWRIGHT_PROXY", None)  # e.g. "http://user:pass@host:port"
USER_AGENT = os.getenv("PLAYWRIGHT_UA", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36")

# Qualification helpers (your rules)
FREE_HOSTS = ["wixsite.com", "wordpress.com", "blogspot.com", "weebly.com", "site123", "webnode", "squarespace", "tumblr"]
def is_free_host(url):
    if not url:
        return False
    u = url.lower()
    return any(h in u for h in FREE_HOSTS)

def is_broken_site(website):
    # minimal quick check: treat None as broken (so qualifies)
    if not website:
        return True
    try:
        if not website.startswith("http"):
            website = "http://" + website
        import requests
        r = requests.get(website, timeout=6, allow_redirects=True)
        if r.status_code != 200:
            return True
        txt = (r.text or "").lower()
        for sig in ("under construction", "coming soon", "domain parked", "404", "not found"):
            if sig in txt:
                return True
        return False
    except Exception:
        return True


# ---------- Helpers to extract details from a place panel ----------
async def _extract_place_from_panel(page):
    """
    When the details panel is open, try:
     - JSON-LD in <script type="application/ld+json">
     - find external links (hrefs not pointing to google)
     - phone numbers via regex
    Returns dict with keys name, website, phone, address
    """
    out = {"name": None, "website": None, "phone": None, "address": None}
    try:
        # try JSON-LD
        jsonld = await page.locator('script[type="application/ld+json"]').all_text_contents()
        for block in jsonld:
            try:
                j = json.loads(block)
                if isinstance(j, dict):
                    out["name"] = out["name"] or j.get("name")
                    out["website"] = out["website"] or j.get("url")
                    out["phone"] = out["phone"] or j.get("telephone")
                    addr = j.get("address")
                    if isinstance(addr, dict):
                        out["address"] = out["address"] or addr.get("streetAddress") or addr.get("addressLocality")
            except Exception:
                continue

        # find external anchors
        anchors = await page.locator('a[href^="http"]').all()
        for a in anchors:
            try:
                href = await a.get_attribute("href")
                if href and "google.com" not in href and "maps" not in href:
                    # prefer websites
                    parsed = urlparse(href)
                    if parsed.scheme.startswith("http"):
                        out["website"] = out["website"] or href
            except:
                continue

        # phone fallback: page content
        content = await page.content()
        m = re.search(r'(\+?\d[\d\-\s]{6,}\d)', content)
        if m and not out["phone"]:
            phone = m.group(1).strip()
            phone = re.sub(r'[\s\-]+', '', phone)
            out["phone"] = phone

        # name fallback: main title element in side panel
        try:
            title = await page.locator('h1, h2, [data-testid="place-card-title"], [aria-label="Place title"]').first.text_content()
            if title:
                out["name"] = out["name"] or title.strip()
        except:
            pass

    except Exception as e:
        # non-fatal — return whatever we have
        # print("panel extraction error:", e)
        pass

    return out


# ---------- Core Playwright scraper ----------
async def _run_playwright_search(query, max_results=120):
    results = []

    pw_opts = {"headless": HEADLESS}
    if PROXY:
        # Playwright format expects dict: {"server": "http://host:port", "username": "...", "password": "..."}
        # Simple pass-through of proxy string is supported for chromium via args, but we will set proxy at browser launch:
        # Format expected below: {"server": PROXY}
        pw_opts["proxy"] = {"server": PROXY}

    # Launch playwright and perform search
    async with async_playwright() as p:
        browser = await p.chromium.launch(**pw_opts, args=["--no-sandbox", "--disable-setuid-sandbox"])
        context = await browser.new_context(user_agent=USER_AGENT, locale="en-US")
        page = await context.new_page()

        search_url = f"https://www.google.com/maps/search/{quote_plus(query)}"
        try:
            await page.goto(search_url, timeout=30000)
        except PWTimeout:
            # early exit
            await browser.close()
            return results

        # Wait for search results list to appear — multiple selectors to be resilient
        try:
            await page.wait_for_selector('a[href*="/place/"], div[role="article"], .Nv2PK', timeout=10000)
        except PWTimeout:
            # no results loaded
            # try to snapshot page for debug but continue
            # print("no search results selector")
            pass

        # Collect candidate place link hrefs from visible list area
        hrefs = set()

        # Strategy: collect anchors in left panel / result list
        anchors = await page.locator('a[href*="/place/"]').all()
        for a in anchors:
            try:
                href = await a.get_attribute("href")
                if href:
                    # sometimes links are relative; construct absolute
                    if href.startswith("/"):
                        href = "https://www.google.com" + href
                    hrefs.add(href)
            except:
                continue

        # Another strategy: collect link-like data from result tiles
        # e.g. div with role=article may contain a nested anchor - evaluate
        try:
            tiles = await page.locator('div[role="article"]').all()
            for t in tiles:
                try:
                    # find anchor inside tile
                    inner = await t.query_selector('a[href*="/place/"]')
                    if inner:
                        h = await inner.get_attribute("href")
                        if h:
                            if h.startswith("/"):
                                h = "https://www.google.com" + h
                            hrefs.add(h)
                except:
                    continue
        except:
            pass

        hrefs = list(hrefs)
        # sometimes the page uses place IDs in data attributes; try to extract them if hrefs empty
        if not hrefs:
            # get page HTML and find /maps/place/ occurrences
            html = await page.content()
            raw_urls = re.findall(r'(https?://www\.google\.[^/]+/maps/place/[^\'"\s<>]+)', html)
            raw_urls = list(dict.fromkeys(raw_urls))
            hrefs = raw_urls

        # Limit candidate urls
        hrefs = hrefs[:max_results]

        # Iterate each place: open in same page (by navigating to URL) or open details in side panel by clicking
        for idx, href in enumerate(hrefs):
            try:
                # navigate to place link so side panel opens with details
                # use goto to ensure panel is loaded
                await page.goto(href, timeout=30000)
                # wait short while for panel to load
                await page.wait_for_timeout(DEFAULT_WAIT)

                # Extract details
                meta = await _extract_place_from_panel(page)

                name = meta.get("name")
                website = meta.get("website")
                phone = meta.get("phone")
                address = meta.get("address")

                # Qualification rules
                if not website:
                    score = 100
                elif is_free_host(website):
                    score = 90
                elif is_broken_site(website):
                    score = 95
                else:
                    # good website -> skip (not target)
                    # but store as rejected entry (not appended)
                    # print("REJECT good site", name, website)
                    await page.wait_for_timeout(DELAY_BETWEEN_ITEMS)
                    continue

                # normalize
                res = {
                    "name": name or None,
                    "category": None,
                    "location": address or query.split(" in ")[-1],
                    "contact": phone,
                    "website": website,
                    "score": score
                }
                results.append(res)

                # polite delay
                await page.wait_for_timeout(int(DELAY_BETWEEN_ITEMS * 1000))

                # stop early if reached desired
                if len(results) >= max_results:
                    break

            except Exception as e:
                # don't break on single failure
                # print("place processing error:", e)
                continue

        try:
            await browser.close()
        except:
            pass

    return results


# ---------- Public sync wrapper ----------
def get_map_results(category, city, max_results=120):
    """
    Synchronous wrapper callable from scheduler.
    Returns list of dicts (not saved to DB).
    """
    q = f"{category} in {city}"
    try:
        return asyncio.run(_run_playwright_search(q, max_results=max_results))
    except Exception:
        # Try fallback with a new loop if already running loop errors
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            res = loop.run_until_complete(_run_playwright_search(q, max_results=max_results))
            loop.close()
            return res
        except Exception as e:
            print("Playwright wrapper error:", e)
            traceback.print_exc()
            return []
