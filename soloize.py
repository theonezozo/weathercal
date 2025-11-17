"""
This module provides functionality to process ICS calendar feeds by removing
past events and stripping attendee information.

The primary use case is to work around Outlook's limitation where it doesn't
import events from Google Calendar ICS feeds if they have attendees.
"""

import datetime
from urllib.parse import urlparse

import ics
import requests


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
    if parsed_url.scheme not in ('http', 'https'):
        raise ValueError("Only HTTP and HTTPS URLs are allowed")
    
    # Prevent access to localhost and private IP ranges
    hostname = parsed_url.hostname
    if not hostname:
        raise ValueError("Invalid URL")
    
    # Block localhost
    if hostname.lower() in ('localhost', '127.0.0.1', '::1'):
        raise ValueError("Access to localhost is not allowed")
    
    # Block private IP ranges (basic check)
    if hostname.startswith('192.168.') or hostname.startswith('10.') or hostname.startswith('172.'):
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
    # Validate the URL first
    validate_url(url)
    
    # Fetch the ICS feed from the provided URL
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    
    # Parse the ICS content
    calendar = ics.Calendar(response.text)
    
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
    
    return new_calendar.serialize()
