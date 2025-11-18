"""
This module provides functionality for caching HTTP requests using the cachetools library.
It defines a TTL (Time-To-Live) cache and a function to fetch the content of a specified URL,
utilizing the cache to avoid redundant network requests.
Attributes:
    CACHE (cachetools.TTLCache): A TTL cache with a maximum size of 10 items and a TTL of 30 minutes.
Functions:
    fetch_url(url): Fetches the content of the specified URL, utilizing the cache to store and retrieve responses.
"""

import threading
import time
from typing import Dict, Set

import cachetools
import requests

FORECAST_CACHE = cachetools.TTLCache(maxsize=10, ttl=3600)  # NWS cache guidance is 1 hour
GRIDPOINT_CACHE = cachetools.TTLCache(
    maxsize=42, ttl=77410
)  # NWS max-age for gridpoints is 21 hours

# Soloize cache for processed calendar feeds
# Using a larger TTL since we'll refresh proactively
SOLOIZE_CACHE: Dict[str, str] = {}
SOLOIZE_CACHE_LOCK = threading.Lock()
SOLOIZE_TRACKED_URLS: Set[str] = set()
SOLOIZE_REFRESH_INTERVAL = 3 * 60 * 60  # 3 hours in seconds


@cachetools.cached(cache=FORECAST_CACHE, info=True)
def fetch_url(url):
    """
    Fetches the content of the specified URL.

    Args:
        url (str): The URL to fetch.

    Returns:
        requests.Response: The response object containing the fetched content.

    Raises:
        requests.HTTPError: If the response status code is not 200.
    """
    return request_url(url)


@cachetools.cached(cache=GRIDPOINT_CACHE, info=True)
def fetch_gridpoint(url):
    return request_url(url)


def request_url(url):
    print("Fetching", url)
    response = requests.get(url, timeout=10)
    if response.status_code != 200:
        response.raise_for_status()
    return response


def get_soloize_cache(url: str) -> str | None:
    """
    Retrieves a cached soloize result for the given URL.

    Args:
        url (str): The calendar URL to retrieve from cache.

    Returns:
        str | None: The cached calendar content or None if not cached.
    """
    with SOLOIZE_CACHE_LOCK:
        return SOLOIZE_CACHE.get(url)


def set_soloize_cache(url: str, content: str) -> None:
    """
    Stores a soloize result in the cache and tracks the URL for proactive refresh.

    Args:
        url (str): The calendar URL.
        content (str): The processed calendar content to cache.
    """
    with SOLOIZE_CACHE_LOCK:
        SOLOIZE_CACHE[url] = content
        SOLOIZE_TRACKED_URLS.add(url)


def get_tracked_urls() -> Set[str]:
    """
    Returns the set of URLs being tracked for proactive refresh.

    Returns:
        Set[str]: A copy of tracked URLs.
    """
    with SOLOIZE_CACHE_LOCK:
        return SOLOIZE_TRACKED_URLS.copy()


def refresh_soloize_cache_background():
    """
    Background thread function that periodically refreshes all tracked soloize feeds.
    Runs every 3 hours and updates the cache for all tracked URLs.
    """
    import soloize  # Import here to avoid circular dependency

    while True:
        time.sleep(SOLOIZE_REFRESH_INTERVAL)

        tracked = get_tracked_urls()
        print(f"Background refresh: updating {len(tracked)} tracked soloize feeds")

        for url in tracked:
            try:
                print(f"Proactively refreshing soloize cache for: {url}")
                result = soloize.fetch_and_process_calendar(url)
                set_soloize_cache(url, result)
                print(f"Successfully refreshed cache for: {url}")
            except Exception as e:
                print(f"Error refreshing cache for {url}: {e}")


def start_background_refresh():
    """
    Starts the background refresh thread for soloize cache.
    Should be called once when the application starts.
    """
    refresh_thread = threading.Thread(
        target=refresh_soloize_cache_background, daemon=True, name="soloize-cache-refresh"
    )
    refresh_thread.start()
    print("Started background soloize cache refresh thread")
