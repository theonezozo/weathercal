"""
This module provides functionality for caching HTTP requests using the cachetools library.
It defines a TTL (Time-To-Live) cache and a function to fetch the content of a specified URL,
utilizing the cache to avoid redundant network requests.
Attributes:
    CACHE (cachetools.TTLCache): A TTL cache with a maximum size of 10 items and a TTL of 30 minutes.
Functions:
    fetch_url(url): Fetches the content of the specified URL, utilizing the cache to store and retrieve responses.
"""

import cachetools
import requests

CACHE = cachetools.TTLCache(maxsize=10, ttl=30 * 60)


@cachetools.cached(cache=CACHE, info=True)
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
    print("Fetching", url)
    response = requests.get(url, timeout=10)
    if response.status_code != 200:
        response.raise_for_status()
    return response
