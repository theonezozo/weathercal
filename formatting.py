import pytz


import datetime


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
