"""
Standalone pagination detection — thin wrapper around listing_scraper internals.
"""

from bs4 import BeautifulSoup
from .listing_scraper import _get_html, _detect_total_pages


def detect_pages(url):
    """
    Open the listing URL and return the total number of pages.
    Returns 1 if no pagination is detected.
    """
    html = _get_html(url)
    soup = BeautifulSoup(html, "html.parser")
    return _detect_total_pages(soup)
