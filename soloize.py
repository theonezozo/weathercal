"""
This module provides functionality to process ICS calendar feeds by removing
past events and stripping attendee information.

The primary use case is to work around Outlook's limitation where it doesn't
import events from Google Calendar ICS feeds if they have attendees.
"""

import datetime
import time
import threading
from urllib.parse import urlparse

import ics
import requests

import cache


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
    cached = cache.get_soloize_cache(url)
    if cached is not None:
        print(f"Returning cached soloize result for {url}")
        return cached
    
    # Not in cache, fetch and process
    print(f"Cache miss for {url}, fetching and processing...")
    result = fetch_and_process_calendar(url)
    
    # Store in cache
    cache.set_soloize_cache(url, result)
    print(f"Cached soloize result for {url}")
    
    return result
