"""
This module provides utility functions for formatting and date calculations.
Constants:
    TIMEZONE_NAME (str): The name of the timezone to use for date calculations.
    EMOJI_WEATHER (dict): A dictionary mapping weather descriptions to their corresponding emoji representations.
"""

import datetime
import hashlib
import uuid

import pytz


def format_range(num1, num2):
    """
    Formats a range of numbers as a string.

    Args:
        num1 (int): The starting number of the range.
        num2 (int): The ending number of the range.

    Returns:
        str: The formatted range string.

    Raises:
        None

    Examples:
        >>> format_range(1, 5)
        '1-5'
        >>> format_range(10, 10)
        '10'
    """
    if num1 == num2:
        return str(num1)
    return f"{num1}-{num2}"


TIMEZONE_NAME = "America/Los_Angeles"
EMOJI_WEATHER = {"Sunny": "☀️", "Mostly Sunny": "🌤", "Partly Sunny": "🌥"}


def this_monday():
    """
    Returns the datetime object representing the start of the current week (Monday at midnight).

    Returns:
        datetime: The datetime object representing the start of the current week.
    """
    # Get the current time
    now = datetime.datetime.now(pytz.timezone(TIMEZONE_NAME))

    # Calculate the number of days to subtract to get to the previous Monday
    days_to_subtract = (now.weekday() - 0) % 7

    # Subtract the necessary days and set the time to midnight
    monday = now - datetime.timedelta(days=days_to_subtract)
    monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)

    return monday


def create_uid(string_to_hash):
    """
    Generates a unique identifier (UUID) based on the SHA-1 hash of the input string.

    Args:
        string_to_hash (str): The input string to be hashed and converted to a UUID.

    Returns:
        str: A UUID generated from the SHA-1 hash of the input string.
    """
    hashed = hashlib.sha1(string_to_hash.encode())
    return str(uuid.UUID(hashed.hexdigest()[:32]))


TIMESTAMP_FORMAT = "%a %b %d %I:%M %p %Z"


def format_timestamp(timezone: str, dt: datetime.datetime) -> str:
    """
    Converts a given datetime object to a specified timezone and formats it as a string.

    Args:
        timezone (str): The timezone to convert the datetime object to.
        dt (datetime.datetime): The datetime object to be converted and formatted.

    Returns:
        str: The formatted datetime string in the specified timezone.
    """
    local_tz = pytz.timezone(timezone)  # Replace with your local timezone
    local_dt = dt.astimezone(local_tz)
    return local_dt.strftime(TIMESTAMP_FORMAT)
