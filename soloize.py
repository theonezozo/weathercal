"""
This module provides functionality to process ICS calendar feeds by removing
past events and stripping attendee information.

The primary use case is to work around Outlook's limitation where it doesn't
import events from Google Calendar ICS feeds if they have attendees.

Caching:
    Implements a simple dictionary-based cache for processed calendar feeds.
    A background thread proactively refreshes tracked URLs every 3 hours
    (SOLOIZE_REFRESH_INTERVAL) to keep the cache warm. Unlike TTL caches,
    entries do not expire automatically—they are only updated by the refresh loop.
"""

import datetime
import threading
import time
from typing import Dict, Set
from urllib.parse import urlparse

import ics
import requests

# Soloize cache for processed calendar feeds
# Using proactive refresh (every 3 hours) instead of TTL expiration
SOLOIZE_CACHE: Dict[str, str] = {}
SOLOIZE_CACHE_LOCK = threading.Lock()
SOLOIZE_TRACKED_URLS: Set[str] = set()
SOLOIZE_REFRESH_INTERVAL = 3 * 60 * 60  # 3 hours in seconds


def validate_url(url: str) -> None:
    """
    Validates a URL to prevent SSRF attacks.

    Args:
        url (str): The URL to validate.

    Raises:
        ValueError: If the URL is invalid or potentially dangerous.
    """
    parsed_url = urlparse(url)

    # Only allow http and https schemes
    if parsed_url.scheme not in ("http", "https"):
        raise ValueError("Only HTTP and HTTPS URLs are allowed")

    # Prevent access to localhost and private IP ranges
    hostname = parsed_url.hostname
    if not hostname:
        raise ValueError("Invalid URL")

    # Block localhost
    if hostname.lower() in ("localhost", "127.0.0.1", "::1"):
        raise ValueError("Access to localhost is not allowed")

    # Block private IP ranges (basic check)
    if hostname.startswith("192.168.") or hostname.startswith("10.") or hostname.startswith("172."):
        raise ValueError("Access to private IP addresses is not allowed")


def fetch_and_process_calendar(url: str) -> str:
    """
    Fetches an ICS calendar from a URL, removes past events and all attendees.

    Args:
        url (str): The URL of the ICS feed to fetch.

    Returns:
        str: The serialized ICS calendar with past events and attendees removed.

    Raises:
        ValueError: If the URL is invalid.
        requests.RequestException: If there's an error fetching the URL.
        Exception: If there's an error parsing the ICS content.
    """
    start_time = time.perf_counter()
    # Validate the URL first
    validate_url(url)

    # Fetch the ICS feed from the provided URL
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    print(
        f"Retrieved ICS feed from {url} with size {len(response.text)} bytes in {time.perf_counter() - start_time:.3f}s"
    )

    # Parse the ICS content
    calendar = ics.Calendar(response.text)
    print("Parsed ICS feed with", len(calendar.events), "events")
    # Get current time for filtering past events
    now = datetime.datetime.now(datetime.timezone.utc)

    # Create a new calendar with filtered events
    new_calendar = ics.Calendar()
    for event in calendar.events:
        # Skip past events (check if event end time or begin time is in the past)
        event_time = event.end if event.end else event.begin
        if event_time and event_time.replace(tzinfo=datetime.timezone.utc) < now:
            continue

        # Remove all attendees
        event.attendees.clear()

        # Add the modified event to the new calendar
        new_calendar.events.add(event)
    print("Filtered calendar has", len(new_calendar.events), "upcoming events")
    duration = time.perf_counter() - start_time
    print(f"fetch_and_process_calendar completed in {duration:.3f}s")
    return new_calendar.serialize()


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

    Runs every 3 hours (SOLOIZE_REFRESH_INTERVAL) and updates the cache for all
    tracked URLs. This proactive refresh ensures that cached content stays fresh
    without relying on TTL expiration.
    """
    while True:
        time.sleep(SOLOIZE_REFRESH_INTERVAL)

        tracked = get_tracked_urls()
        print(f"Background refresh: updating {len(tracked)} tracked soloize feeds")

        for url in tracked:
            try:
                print(f"Proactively refreshing soloize cache for: {url}")
                result = fetch_and_process_calendar(url)
                set_soloize_cache(url, result)
                print(f"Successfully refreshed cache for: {url}")
            except (requests.RequestException, ValueError, KeyError) as e:
                print(f"Error refreshing cache for {url}: {e}")


def start_background_refresh():
    """
    Starts the background refresh thread for soloize cache.

    Should be called once when the application starts. The thread runs as a daemon,
    so it will automatically terminate when the main application exits.
    """
    refresh_thread = threading.Thread(
        target=refresh_soloize_cache_background, daemon=True, name="soloize-cache-refresh"
    )
    refresh_thread.start()
    print("Started background soloize cache refresh thread")


def fetch_and_process_calendar_cached(url: str) -> str:
    """
    Fetches and processes an ICS calendar with caching support.

    This function implements a cache-first strategy:
    1. Returns cached result immediately if available
    2. If not cached, fetches and processes the calendar, then caches it
    3. Starts background tracking for proactive refresh

    Args:
        url (str): The URL of the ICS feed to fetch.

    Returns:
        str: The serialized ICS calendar with past events and attendees removed.

    Raises:
        ValueError: If the URL is invalid.
        requests.RequestException: If there's an error fetching the URL.
        Exception: If there's an error parsing the ICS content.
    """
    # Try to get from cache first
    cached = get_soloize_cache(url)
    if cached is not None:
        print(f"Returning cached soloize result for {url}")
        return cached

    # Not in cache, fetch and process
    print(f"Cache miss for {url}, fetching and processing...")
    result = fetch_and_process_calendar(url)

    # Store in cache
    set_soloize_cache(url, result)
    print(f"Cached soloize result for {url}")

    return result
