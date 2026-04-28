"""
DEPRECATED — replaced by overpass_scraper.py and yellowpages_scraper.py
which provide the same data for FREE without API keys.

This file is kept as an optional paid fallback. Set GOOGLE_PLACES_API_KEY
in .env to enable. The free scrapers above will cover most use cases.
"""

import os
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "")


def find_businesses_without_websites(state="MA", categories=None, max_per_city=10):
    """Stub — use overpass_scraper or yellowpages_scraper instead (both free)."""
    return []
