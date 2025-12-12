# client_hunter/app/scraper/osm_scraper.py
"""
OSM / Overpass scraper for Client Hunter.

- Uses Nominatim to resolve city -> bounding box
- Uses Overpass API to query for businesses matching category tags
- Extracts name, website, phone, address
- Applies qualification rules:
     * keep if NO website
     * keep if FREE-HOST website (wix/wordpress/blogspot/etc)
     * keep if BROKEN website (simple check)
- Saves leads into Lead model (app.models.Lead)

Usage:
    from app.scraper.osm_scraper import get_osm_results
    results = get_osm_results("mobile repair", "Pune", max_results=120)
"""

import time
import re
import requests
from urllib.parse import quote_plus
from app.db import db
from app.models import Lead

# polite user agent (include contact if you have one)
UA = "ClientHunter/1.0 (+https://example.com) (your-email@example.com)"

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": UA,
    "Accept-Language": "en",
})

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
NOMINATIM_SEARCH = "https://nominatim.openstreetmap.org/search"

FREE_HOST_PATTERNS = [
    "wixsite.com", "wordpress.com", "blogspot.com", "weebly.com",
    "site123.me", "webnode.com", "tumblr.com", "squarespace.com"
]

BROKEN_SIGNS = [
    "under construction", "coming soon", "maintenance",
    "domain parked", "page not found", "this domain is for sale", "404"
]

# Map your semantic categories to possible OSM tags.
# This is best-effort and you can add more keys/values
CATEGORY_OSM_MAPPING = {
    "mobile repair": [
        ('shop', 'mobile_phone'),
        ('shop', 'electronics'),
        ('service', 'mobile_phone_repair'),
    ],
    "electronics repair": [
        ('shop', 'electronics'),
        ('service', 'electronics_repair'),
        ('shop', 'computer'),
    ],
    "home appliances repair": [
        ('service', 'appliance_repair'),
        ('shop', 'electronics'),
    ],
    "salons": [
        ('shop', 'beauty'),
        ('shop', 'hairdresser'),
        ('amenity', 'beauty_salon'),
    ],
    "gyms": [
        ('leisure', 'fitness_centre'),
        ('sport', 'gym'),
        ('leisure', 'gym'),
    ],
    "restaurants": [
        ('amenity', 'restaurant'),
        ('amenity', 'fast_food'),
        ('amenity', 'cafe'),
    ],
    "clinics": [
        ('amenity', 'clinic'),
        ('amenity', 'doctors'),
    ],
    "car repair": [
        ('shop', 'car_repair'),
        ('shop', 'car'),
        ('service', 'car_repair'),
    ],
    "coaching centers": [
        ('amenity', 'school'),
        ('office', 'training'),
    ],
    "cafes": [
        ('amenity', 'cafe'),
    ],
    "tutors": [
        ('amenity', 'school'),
        ('office', 'training'),
    ],
    "plumbers": [
        ('trade', 'plumber'),
        ('service', 'plumber'),
    ],
    "electricians": [
        ('trade', 'electrician'),
        ('service', 'electrician'),
    ],
    "pet grooming": [
        ('shop', 'pet'),
        ('shop', 'pet_grooming'),
    ],
}


# ----------------------------
# Helpers: Nominatim bbox
# ----------------------------
def city_to_bbox(city_name, country=None):
    """
    Return bounding box (south, west, north, east) for a city using Nominatim.
    """
    params = {"q": city_name, "format": "json", "limit": 1}
    if country:
        params["country"] = country

    try:
        r = SESSION.get(NOMINATIM_SEARCH, params=params, timeout=15)
        if r.status_code != 200:
            print("[OSM] Nominatim returned", r.status_code)
            return None
        data = r.json()
        if not data:
            print("[OSM] Nominatim: no results for", city_name)
            return None
        item = data[0]
        bbox = item.get("boundingbox")  # [south, north, west, east] strings
        # convert to floats and reorder to (south, west, north, east)
        south = float(bbox[0])
        north = float(bbox[1])
        west = float(bbox[2])
        east = float(bbox[3])
        return (south, west, north, east)
    except Exception as e:
        print("[OSM] city_to_bbox error:", e)
        return None


# ----------------------------
# Helpers: build overpass query
# ----------------------------
def build_overpass_query(osm_pairs, bbox, max_results=120):
    """
    osm_pairs: list of (k,v) pairs to search, e.g. ('shop','electronics')
    bbox: (south, west, north, east)
    returns Overpass QL string
    """
    south, west, north, east = bbox
    # Build union of node/way/relation queries
    parts = []
    for k, v in osm_pairs:
        # match exact key/value and also some relaxed patterns
        parts.append(f'node["{k}"="{v}"]({south},{west},{north},{east});')
        parts.append(f'way["{k}"="{v}"]({south},{west},{north},{east});')
        parts.append(f'relation["{k}"="{v}"]({south},{west},{north},{east});')

    # wrap and limit
    q = "[out:json][timeout:25];(" + "".join(parts) + ");out center qt %d;" % max_results
    return q


# ----------------------------
# Helpers: parse Overpass results
# ----------------------------
def parse_overpass_result(data):
    """
    data is the JSON dict returned by Overpass.
    Return list of dicts with fields: name, website, phone, address
    """
    out = []
    elements = data.get("elements", [])
    for el in elements:
        tags = el.get("tags", {}) or {}
        name = tags.get("name")
        website = tags.get("website") or tags.get("contact:website") or tags.get("url")
        phone = tags.get("phone") or tags.get("contact:phone")
        # build address from tags if present
        addr_parts = []
        for t in ("addr:street", "addr:housenumber", "addr:city", "addr:postcode"):
            if tags.get(t):
                addr_parts.append(tags.get(t))
        address = ", ".join(addr_parts) if addr_parts else tags.get("addr:full") or tags.get("address")
        out.append({
            "name": name,
            "website": website,
            "phone": phone,
            "address": address,
            "tags": tags
        })
    return out


# ----------------------------
# Helpers: website checks
# ----------------------------
def _is_free_host(url):
    if not url:
        return False
    u = url.lower()
    return any(p in u for p in FREE_HOST_PATTERNS)


def _is_broken_website(url):
    if not url:
        return True
    try:
        # normalize
        if not url.startswith("http"):
            url = "http://" + url
        r = SESSION.get(url, timeout=8, allow_redirects=True)
        if r.status_code != 200:
            return True
        text = r.text.lower()
        for sig in BROKEN_SIGNS:
            if sig in text:
                return True
        return False
    except Exception:
        return True


# ----------------------------
# Save helper
# ----------------------------
def save_if_qualified(item, category, default_location):
    """
    item: dict with keys name, website, phone, address
    Save into Lead only if qualifies per your rules.
    """
    name = item.get("name")
    website = item.get("website")
    phone = item.get("phone")
    address = item.get("address") or default_location

    # Reject if no name
    if not name:
        return None

    # Apply qualification rules:
    # Keep if NO website OR free-host OR broken
    qualified = False
    if not website:
        qualified = True
        score = 100
    elif _is_free_host(website):
        qualified = True
        score = 90
    elif _is_broken_website(website):
        qualified = True
        score = 95
    else:
        qualified = False
        score = 0

    if not qualified:
        # not a target lead
        return None

    # dedupe by phone or name+location
    if phone:
        existing = Lead.query.filter_by(contact=phone).first()
        if existing:
            return None

    existing = Lead.query.filter_by(name=name, location=address).first()
    if existing:
        return None

    lead = Lead(
        name=name,
        category=category.title() if isinstance(category, str) else category,
        location=address,
        contact=phone,
        website=website,
        social_links=None,
        source="osm_overpass",
        priority_score=score,
        status="new"
    )
    db.session.add(lead)
    db.session.commit()
    print("[OSM] SAVED:", name, "| score:", score)
    return lead


# ----------------------------
# Main entrypoint
# ----------------------------
def get_osm_results(category, city, max_results=120, country=None):
    """
    category: human string, e.g. "mobile repair"
    city: city name
    max_results: overall cap per category
    country: optional country name to narrow nominatim
    """
    print(f"[OSM] Querying category='{category}' city='{city}' max={max_results}")

    # 1) resolve bbox
    bbox = city_to_bbox(city) if not country else city_to_bbox(f"{city}, {country}")
    if not bbox:
        print("[OSM] Could not resolve city bbox; aborting.")
        return []

    # 2) build list of OSM tag pairs for this category
    osmpairs = CATEGORY_OSM_MAPPING.get(category.lower(), None)
    if not osmpairs:
        # fallback: try "shop" equal to category slug
        guess_key = category.lower().replace(" ", "_")
        osmpairs = [('shop', guess_key)]

    # 3) iterate over osmpairs and collect results until max_results
    collected = []
    remaining = max_results
    for osm_pair in osmpairs:
        if remaining <= 0:
            break

        # Build query for this single pair (as list with one pair)
        q = build_overpass_query([osm_pair], bbox, max_results=remaining)
        try:
            r = SESSION.post(OVERPASS_URL, data=q.encode('utf-8'), headers={"User-Agent": UA}, timeout=60)
            if r.status_code != 200:
                print("[OSM] Overpass returned", r.status_code)
                # polite backoff and continue
                time.sleep(1)
                continue
            data = r.json()
        except Exception as e:
            print("[OSM] Overpass error:", e)
            time.sleep(1)
            continue

        items = parse_overpass_result(data)
        print(f"[OSM] Overpass returned {len(items)} items for tag {osm_pair}")
        for it in items:
            if len(collected) >= max_results:
                break
            saved = save_if_qualified(it, category, city)
            if saved:
                collected.append(saved)

        remaining = max_results - len(collected)
        # polite pause
        time.sleep(1)

    print(f"[OSM] Finished. saved_total={len(collected)}")
    return collected


# CLI friendly
if __name__ == "__main__":
    # quick test
    out = get_osm_results("mobile repair", "Pune", max_results=50)
    print("Saved:", len(out))
