"""
This module provides functionality for caching HTTP requests using the cachetools library.
It defines TTL (Time-To-Live) caches for National Weather Service (NWS) API endpoints
to avoid redundant network requests and comply with NWS caching guidance.

Attributes:
    FORECAST_CACHE (cachetools.TTLCache): Cache for NWS forecast data (1 hour TTL).
    GRIDPOINT_CACHE (cachetools.TTLCache): Cache for NWS gridpoint data (21 hour TTL).

Functions:
    fetch_url(url): Fetches NWS forecast URL content with caching.
    fetch_gridpoint(url): Fetches NWS gridpoint URL content with caching.
    request_url(url): Base HTTP GET function with error handling.
"""

import cachetools
import requests

FORECAST_CACHE = cachetools.TTLCache(maxsize=10, ttl=3600)  # NWS cache guidance is 1 hour
GRIDPOINT_CACHE = cachetools.TTLCache(
    maxsize=42, ttl=77410
)  # NWS max-age for gridpoints is 21 hours


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
    """
    Fetch gridpoint data from the National Weather Service API.

    Args:
        url (str): The URL endpoint for the gridpoint data request.

    Returns:
        The response from the gridpoint API endpoint via request_url function.

    Raises:
        Any exceptions that may be raised by the underlying request_url function.
    """
    return request_url(url)


def request_url(url):
    """
    Fetches content from a URL with error handling.

    Makes an HTTP GET request to the specified URL with a 10-second timeout.
    Prints the URL being fetched for debugging purposes. Raises an exception
    if the response status code is not 200 (OK).

    Args:
        url (str): The URL to fetch content from.

    Returns:
        requests.Response: The response object from the HTTP request.

    Raises:
        requests.exceptions.HTTPError: If the response status code is not 200.
        requests.exceptions.Timeout: If the request times out after 10 seconds.
        requests.exceptions.RequestException: For other request-related errors.
    """
    print("Fetching", url)
    response = requests.get(url, timeout=10)
    if response.status_code != 200:
        response.raise_for_status()
    return response
