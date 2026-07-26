import logging
import os

import httpx

logger = logging.getLogger(__name__)

GEOCODING_ENDPOINT = "https://maps.googleapis.com/maps/api/geocode/json"


def geocode(address):
    """
    Convert a Japanese address string to (lat, lng).
    Returns (lat, lng) tuple or None on failure.
    """
    if not address:
        return None

    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        logger.error("GOOGLE_MAPS_API_KEY が設定されていません")
        return None

    try:
        response = httpx.get(
            GEOCODING_ENDPOINT,
            params={
                "address": address,
                "key": api_key,
                "language": "ja",
            },
            timeout=10,
        )
        data = response.json()

        if data["status"] == "OK" and data["results"]:
            loc = data["results"][0]["geometry"]["location"]
            return loc["lat"], loc["lng"]

        logger.debug(f"  Geocoding失敗 ({data['status']}): {address[:50]}")
    except Exception as e:
        logger.warning(f"  Geocoding例外: {e}")

    return None
