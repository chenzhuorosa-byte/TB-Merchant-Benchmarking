"""
Scrapes one Talabat restaurant listing page.
Returns basic card data for every restaurant PLUS the URL to that
restaurant's detail page (used by detail_scraper in Phase 2).
"""

import re
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

from . import selectors_listing as sel


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_listing(url):
    """
    Step 1 (listing side): open one listing page and return field samples
    plus the total number of pages.

    Returns:
        fields  (dict) — {field_key: {label, description, samples, found}}
        total_pages (int)
    """
    html  = _get_html(url)
    soup  = BeautifulSoup(html, "html.parser")
    cards = _find_cards(soup)

    if not cards:
        raise ValueError(
            "No restaurant listings found. "
            "Make sure the URL is a Talabat restaurant listing page, "
            "e.g. https://www.talabat.com/kuwait/restaurants/52/mirqab"
        )

    fields = {}
    for key, defn in sel.FIELDS.items():
        samples = []
        for card in cards[:5]:
            val = _extract_field(card, key)
            if val and val not in samples:
                samples.append(val)
        fields[key] = {
            "label":       defn["label"],
            "description": defn["description"],
            "samples":     samples[:3],
            "found":       len(samples) > 0,
        }

    return fields, _detect_total_pages(soup)


def scrape_page(url, selected_fields):
    """
    Scrape one listing page.

    Returns a list of dicts, one per restaurant card:
        {
          "merchant_url": "https://www.talabat.com/kuwait/restaurant/…",
          "listing_data": {field_key: value, …}   ← only selected_fields
        }
    """
    html  = _get_html(url)
    soup  = BeautifulSoup(html, "html.parser")
    cards = _find_cards(soup)

    results = []
    for card in cards:
        listing_data = {f: _extract_field(card, f) for f in selected_fields}
        merchant_url = _extract_merchant_url(card)
        if merchant_url:
            results.append({
                "merchant_url": merchant_url,
                "listing_data": listing_data,
            })
    return results


# ---------------------------------------------------------------------------
# Browser
# ---------------------------------------------------------------------------

def _get_html(url):
    """Open the URL with stealth settings and return rendered HTML."""
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 900},
            locale="en-US",
            timezone_id="Asia/Kuwait",
        )
        ctx.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
        )
        page = ctx.new_page()
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2500)
        html = page.content()
        browser.close()
    return html


# ---------------------------------------------------------------------------
# Card detection
# ---------------------------------------------------------------------------

def _find_cards(soup):
    return soup.find_all("a", attrs={"data-testid": sel.CARD_TESTID})


def _extract_merchant_url(card):
    """Return the absolute URL to the restaurant's detail page."""
    href = card.get("href", "")
    if href:
        if href.startswith("http"):
            return href
        return "https://www.talabat.com" + href
    return ""


# ---------------------------------------------------------------------------
# Field extraction
# ---------------------------------------------------------------------------

def _extract_field(card, field_key):
    if field_key == "name":
        return _name(card)
    if field_key == "cuisine":
        return _cuisine(card)
    if field_key == "rating":
        return _rating(card)
    if field_key == "delivery_time":
        return _delivery_time(card)
    if field_key == "delivery_fee":
        return _delivery_fee(card)
    if field_key == "minimum_order":
        return _minimum_order(card)
    return ""


def _name(card):
    h2 = card.find("h2")
    return h2.get_text(strip=True) if h2 else ""


def _cuisine(card):
    content = card.find("div", class_=sel.CONTENT_CLASS)
    if content:
        h2 = content.find("h2")
        if h2:
            sib = h2.find_next_sibling("div")
            if sib:
                return sib.get_text(strip=True)
    return ""


def _rating(card):
    comp = card.find(attrs={"data-testid": sel.RATING_TESTID})
    return comp.get_text(strip=True) if comp else ""


def _delivery_time(card):
    for span in card.find_all("span"):
        m = re.search(r"Within\s+(\d+)\s+min", span.get_text(strip=True), re.I)
        if m:
            return f"{m.group(1)} min"
    return ""


def _delivery_fee(card):
    for span in card.find_all("span"):
        m = re.match(r"Delivery[:\s]+(.+)", span.get_text(strip=True), re.I)
        if m:
            return m.group(1).strip()
    return ""


def _minimum_order(card):
    for span in card.find_all("span"):
        m = re.match(r"Min[:\s]+(.+)", span.get_text(strip=True), re.I)
        if m:
            return m.group(1).strip()
    return ""


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

def _detect_total_pages(soup):
    """Read the numeric `page` attribute from pagination <li> items."""
    page_numbers = []
    for li in soup.find_all("li", attrs={"data-testid": "paginate-link"}):
        a = li.find("a", attrs={"page": True})
        if a and a["page"].isdigit():
            page_numbers.append(int(a["page"]))
    if not page_numbers:
        for a in soup.find_all("a", href=True):
            m = re.search(r"[?&]page=(\d+)", a["href"])
            if m:
                page_numbers.append(int(m.group(1)))
    return max(page_numbers) if page_numbers else 1
