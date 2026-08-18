"""
Scrapes one Talabat restaurant detail page.

Data extraction strategy (in priority order):
  1. JSON-LD structured data  - most reliable, machine-readable
  2. data-testid attributes   - confirmed against live page dump
"""

import json as _json
import re
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

from . import selectors_detail as sel


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_detail(url):
    """
    Step 1 (detail side): open one example detail page and return
    field samples so the user can see what data is available.

    Returns:
        fields (dict) -- {field_key: {label, description, samples, found}}
    """
    html = _get_html(url)
    soup = BeautifulSoup(html, "html.parser")

    fields = {}
    for key, defn in sel.FIELDS.items():
        val = _extract_field(soup, key)
        fields[key] = {
            "label":       defn["label"],
            "description": defn["description"],
            "samples":     [val] if val else [],
            "found":       bool(val),
        }
    return fields


def scrape_detail(url, selected_fields):
    """
    Scrape one detail page and return a dict of only the selected fields.
    Returns empty strings for all fields if the page fails to load.
    """
    try:
        html = _get_html(url)
    except Exception:
        return {f: "" for f in selected_fields}

    soup = BeautifulSoup(html, "html.parser")
    return {f: _extract_field(soup, f) for f in selected_fields}


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
        page.wait_for_timeout(2000)
        html = page.content()
        browser.close()
    return html


# ---------------------------------------------------------------------------
# JSON-LD extraction  (primary source)
# ---------------------------------------------------------------------------

def _parse_json_ld(soup):
    """
    Find the Restaurant JSON-LD block and return a flat dict.
    Returns {} if not found or not a Restaurant type.
    """
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = _json.loads(script.string or "")
        except Exception:
            continue
        if data.get("@type") != "Restaurant":
            continue

        result = {}

        addr = data.get("address", {})
        result["address"] = addr.get("streetAddress", "")
        result["area"]    = addr.get("addressLocality", "")

        tel = data.get("telephone", "")
        # Filter out Talabat placeholder "00000-00000"
        result["phone"] = "" if re.fullmatch(r"0+[-0]+", tel) else tel

        geo = data.get("geo", {})
        result["latitude"]  = geo.get("latitude", "")
        result["longitude"] = geo.get("longitude", "")

        return result
    return {}


# ---------------------------------------------------------------------------
# DOM extraction  (secondary source, data-testid)
# ---------------------------------------------------------------------------

def _extract_area_from_dom(soup):
    """
    The area text lives inside a <small> tag within the restaurant-title element.

    Raw HTML (simplified):
        <h1 data-testid="restaurant-title">
          &Cookies<br>
          <small class="light-text">in&nbsp;Hawally&nbsp;,&nbsp;Kuwait</small>
        </h1>

    We split on whitespace so &nbsp; chars (U+00A0) become word separators,
    then rejoin cleanly.
    """
    title = soup.find(attrs={"data-testid": sel.TITLE_TESTID})
    if not title:
        return ""
    small = title.find("small")
    if not small:
        return ""

    # get_text(separator=" ") converts &nbsp; entities to spaces
    raw = small.get_text(separator=" ")

    # Split on any whitespace (including U+00A0) and rejoin with single spaces
    words = raw.split()
    text = " ".join(words)

    # Remove spurious space before comma: "Hawally , Kuwait" -> "Hawally, Kuwait"
    text = re.sub(r" ,", ",", text)

    # Strip leading "in " that Talabat prepends to the location
    text = re.sub(r"^in ", "", text, flags=re.IGNORECASE)

    return text.strip()


def _extract_open_status(soup):
    el = soup.find(attrs={"data-testid": sel.STATUS_TESTID})
    if el:
        text = el.get_text(strip=True)
        return text if text else "Unknown"
    return ""


def _extract_payment_methods(soup):
    """Find all payment-image-* testid attributes and map to friendly names."""
    wrapper = soup.find(attrs={"data-testid": sel.PAYMENT_TESTID})
    if not wrapper:
        return ""
    methods = []
    for img in wrapper.find_all(attrs={"data-testid": True}):
        tid = img["data-testid"]
        if tid.startswith(sel.PAYMENT_IMG_PREFIX):
            slug = tid[len(sel.PAYMENT_IMG_PREFIX):]
            label = sel.PAYMENT_LABELS.get(slug, slug.replace("-", " ").title())
            methods.append(label)
    return ", ".join(methods)


# ---------------------------------------------------------------------------
# Field dispatcher
# ---------------------------------------------------------------------------

def _extract_field(soup, field_key):
    """Extract one field, trying JSON-LD first then DOM fallback."""
    jld = _parse_json_ld(soup)

    if field_key == "area":
        # DOM shows the restaurant's own neighbourhood ("Hawally").
        # JSON-LD addressLocality can reflect the listing area instead ("Mirqab").
        return _extract_area_from_dom(soup) or jld.get("area", "")

    if field_key == "address":
        return jld.get("address", "")

    if field_key == "phone":
        return jld.get("phone", "")

    if field_key == "latitude":
        return jld.get("latitude", "")

    if field_key == "longitude":
        return jld.get("longitude", "")

    if field_key == "payment_methods":
        return _extract_payment_methods(soup)

    if field_key == "open_status":
        return _extract_open_status(soup)

    return ""
