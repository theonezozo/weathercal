"""
This module provides functionality to fetch weather data from the National Weather Service (NWS) API,
process the data, and generate calendars of weather events based on specific criteria such as rain,
warm weather, cool weather, comfortable weather, and weather alerts.
"""

import datetime
import json
import re
from typing import Tuple

import flask
import ics
import pytz
import requests

import cache
from formatting import TIMEZONE_NAME, create_uid, format_range

MIN_CHANCE_RAIN = 33
MIN_WARM_TEMP = 68  # in F
MAX_COOL_TEMP = 72  # in F
MAX_COOL_DEWPOINT = 15.5556  # in C

SHORT_FORECAST = "shortForecast"

# Default gridpoint for fetching weather data: downtown Mountain View, CA, USA.
DEFAULT_GRIDPOINT = {
    "forecastHourly": "https://api.weather.gov/gridpoints/MTR/93,86/forecast/hourly",
    "timeZone": "America/Los_Angeles",
}

# URLs for fetching weather forecasts. For now, they're hard-coded to downtown Mountain View, CA, USA.
URL = "https://api.weather.gov/gridpoints/MTR/93,86/forecast/hourly"
ALERT_URL = "https://api.weather.gov/alerts/active/zone/CAZ508"


def fetch_url(url: str) -> requests.Response:
    """
    Fetches the content from the given URL using a caching mechanism.

    Args:
        url (str): The URL to fetch.

    Returns:
        requests.Response: The response object containing the fetched content.

    Raises:
        requests.RequestException: If there is an error during the request,
                                   it prints the error and aborts the request
                                   with the appropriate status code and message.
    """
    try:
        return cache.fetch_url(url)
    except requests.RequestException as err:
        print("Error:", err)
        response = err.response
        flask.abort(response.status_code, response.text)


def get_rain_calendar(gridpoint: dict = None) -> str:
    """
    Builds a calendar of rainy weather events.

    This function fetches weather data from a specified URL, filters the data to identify rainy weather events,
    and then serializes the resulting calendar of these events.

    Returns:
        str: A serialized calendar of rainy weather events.
    """
    if gridpoint is None:
        gridpoint = DEFAULT_GRIDPOINT
    url = gridpoint["forecastHourly"]
    return build_interesting_weather_calendar(
        is_rainy, fetch_url(url), timezone=gridpoint["timeZone"]
    ).serialize()


def is_rainy(period: dict) -> bool:
    """
    Determines if the given period has a high probability of rain.

    Args:
        period (dict): A dictionary containing weather information for a specific period.
                       It should have a key "probabilityOfPrecipitation" which is a dictionary
                       containing a key "value" representing the probability of precipitation as a percentage.

    Returns:
        bool: True if the probability of precipitation is greater than MIN_CHANCE_RAIN, False otherwise.
    """
    return period["probabilityOfPrecipitation"]["value"] > MIN_CHANCE_RAIN


def get_warm_calendar() -> str:
    """
    Generates a serialized calendar of interesting warm weather events.

    This function fetches weather data from a specified URL, filters for warm weather events,
    and builds a calendar of these events. The calendar is then serialized to a string format.

    Returns:
        str: A serialized string representation of the warm weather events calendar.
    """
    return build_interesting_weather_calendar(is_warm, fetch_url(URL)).serialize()


def is_warm(period):
    return period["temperature"] >= MIN_WARM_TEMP


def get_cool_calendar() -> str:
    return build_interesting_weather_calendar(is_cool, fetch_url(URL)).serialize()


def is_cool(period: dict) -> bool:
    """
    Determines if the given weather period is considered cool based on temperature and dewpoint.

    Args:
        period (dict): A dictionary containing weather information for a specific period.
                       It should have the keys "temperature" and "dewpoint", where "dewpoint"
                       is a dictionary with a "value" key.

    Returns:
        bool: True if the period's temperature is less than or equal to MAX_COOL_TEMP and
              the dewpoint value is less than or equal to MAX_COOL_DEWPOINT, otherwise False.
    """
    return (
        period["temperature"] <= MAX_COOL_TEMP and period["dewpoint"]["value"] <= MAX_COOL_DEWPOINT
    )


def get_comfort_calendar() -> str:
    return build_interesting_weather_calendar(is_comfortable, fetch_url(URL)).serialize()


def is_comfortable(period):
    return MIN_WARM_TEMP <= period["temperature"] <= MAX_COOL_TEMP


def get_alert_calendar() -> str:
    """
    Fetches weather alert data from a predefined URL, builds a calendar of alerts,
    and returns the serialized calendar as a string.

    Returns:
        str: The serialized calendar containing weather alerts.
    """
    return build_alert_calendar(fetch_url(ALERT_URL)).serialize()


def build_alert_calendar(response) -> ics.Calendar:
    """
    Builds an ics.Calendar object of weather alerts from the given response.

    Args:
        response: The response object containing the data.

    Returns:
        An ics.Calendar object representing the alert calendar.
    """
    data = json.loads(response.content)
    calendar = ics.Calendar()
    for feature in data["features"]:
        properties = feature["properties"]
        event = ics.Event()
        event.name = properties["event"]
        event.begin = properties["onset"]
        event.end = properties["ends"] or properties["expires"]  # ends
        event.description = re.sub(
            r"(?<!\n)\n(?!\n)", " ", properties["description"], 0, re.MULTILINE
        )
        calendar.events.add(event)
    return calendar


def get_best_weather_calendar() -> str:
    return build_best_weather_calendar(fetch_url(URL)).serialize()


def build_best_weather_calendar(response):
    """
    Builds a calendar object with the best weather forecast events.

    Args:
        response (Response): The response object containing the weather forecast data.

    Returns:
        Calendar: The calendar object with the best weather forecast events.
    """
    data = json.loads(response.content)
    forecast_updated = get_forecast_timestamp(data)
    calendar = ics.Calendar()
    for day in days(data["properties"]["periods"]):
        best_period = sorted(day, key=forecast_desirability)[0]
        start_time = best_period["startTime"]
        event = ics.Event(uid=create_uid(start_time[:10]))
        forecast = best_period["shortForecast"]
        temp = best_period["temperature"]
        prob_precip = best_period["probabilityOfPrecipitation"]["value"]

        event.name = forecast
        event.begin = start_time
        event.end = best_period["endTime"]
        event.description = (
            f"{temp}F, {prob_precip}% chance of rain\nForecast updated {forecast_updated}"
        )
        calendar.events.add(event)
    return calendar


def weather_blocks(periods, interest_fn):
    """
    Yields contiguous blocks of events that have similar weather events.

    Args:
        periods (list): A list of periods representing time intervals.
        interest_fn (function): A function that determines whether a period is of interest.

    Yields:
        list: A block of events that have similar weather events.

    """
    current_block = []
    for period in periods:
        of_interest = interest_fn(period)
        rain_interest = interest_fn is is_rainy
        forecast = period[SHORT_FORECAST]
        if of_interest:  # this is an hour we'd consider interesting
            # For rainy weather blocks, the shortForecast must match.
            if current_block and (
                not rain_interest or current_block[0][SHORT_FORECAST] == forecast
            ):
                # we can add this hour to the current block
                current_block.append(period)
            else:
                # we need to start a new block
                if current_block:
                    yield current_block
                current_block = [period]
        else:  # this is no longer an interesting period
            if current_block:
                yield current_block
                current_block = []  # reset
    if current_block:
        yield current_block


def days(periods):
    """
    Groups periods based on their start date and yields a list of periods for each day.

    Args:
        periods (list): A list of periods.

    Yields:
        list: A list of periods for each day.

    Example:
        periods = [
            {'startTime': '2022-01-01T08:00:00', 'isDaytime': True},
            {'startTime': '2022-01-01T12:00:00', 'isDaytime': True},
            {'startTime': '2022-01-02T08:00:00', 'isDaytime': True},
            {'startTime': '2022-01-02T12:00:00', 'isDaytime': True},
            {'startTime': '2022-01-03T08:00:00', 'isDaytime': True},
        ]

        for day in days(periods):
            print(day)

        Output:
        [{'startTime': '2022-01-01T08:00:00', 'isDaytime': True}, {'startTime': '2022-01-01T12:00:00', 'isDaytime': True}]
        [{'startTime': '2022-01-02T08:00:00', 'isDaytime': True}, {'startTime': '2022-01-02T12:00:00', 'isDaytime': True}]
        [{'startTime': '2022-01-03T08:00:00', 'isDaytime': True}]
    """
    current_day = []
    current_date = None
    for period in periods:
        if not period["isDaytime"]:
            continue
        start_time = period["startTime"]
        this_date: object = start_time.split("T")[0]
        if current_date != this_date:
            if current_day:
                yield current_day
            current_day = [period]
            current_date = this_date
        else:
            current_day.append(period)
    yield current_day


def forecast_desirability(period):
    """
    Derives a sortable desirability key for a given period based on its weather forecast.

    Args:
        period (dict): A dictionary containing weather attributes for a specific period.

    Returns:
        tuple: A tuple containing the calculated values for probability of precipitation,
               temperature discomfort, and wind speed.

    """
    # Treat low probability of rain forecasts as equivalent
    prob_precip = max(period["probabilityOfPrecipitation"]["value"], MIN_CHANCE_RAIN)
    temp_discomfort = abs(70 - period["temperature"])
    wind_speed = int(period["windSpeed"].split(" ")[0])
    return prob_precip, temp_discomfort, wind_speed


def get_forecast_timestamp(data, timezone=TIMEZONE_NAME):
    """
    Converts the 'updated' timestamp from the given data object to a localized format.

    Args:
        data (dict): The data containing the 'updated' timestamp.

    Returns:
        str: The localized timestamp in the format: 'Wed Apr 03 03:32 PM'.
    """
    updated = data["properties"]["updateTime"]
    dt = datetime.datetime.strptime(updated, "%Y-%m-%dT%H:%M:%S%z")
    local_tz = pytz.timezone(timezone)  # Replace with your local timezone
    local_dt = dt.astimezone(local_tz)
    forecast_updated = local_dt.strftime("%a %b %d %I:%M %p")
    return forecast_updated


def build_interesting_weather_calendar(
    interest_fn, response, timezone: str = TIMEZONE_NAME
) -> ics.Calendar:
    """
    Builds an interesting weather calendar based on the provided interest function and weather response.

    Args:
        interest_fn (function): The interest function used to determine interesting weather conditions.
        response (object): The HTTP response object.

    Returns:
        ics.Calendar: The calendar containing interesting weather events.
    """
    data = json.loads(response.content)
    forecast_updated = get_forecast_timestamp(data, timezone)
    calendar = ics.Calendar()
    for block in weather_blocks(data["properties"]["periods"], interest_fn):
        start_time = block[0]["startTime"]
        end_time = block[-1]["endTime"]
        event_name = ""
        if interest_fn is is_rainy:
            event_name = block[0]["shortForecast"]
        elif interest_fn is is_warm:
            event_name = "Open 🪟 for ♨️"
        elif interest_fn is is_cool:
            event_name = "Open 🪟 for 🆒"
        elif interest_fn is is_comfortable:
            event_name = "Open 🪟"

        event = ics.Event(uid=create_uid(f"{event_name}{start_time}{end_time}"))
        event.name = event_name
        event.begin = start_time
        event.end = end_time
        pops = [period["probabilityOfPrecipitation"]["value"] for period in block]
        temps = [period["temperature"] for period in block]
        event.description = (
            f"{format_range(min(temps), max(temps))}F\n"
            f"{format_range(min(pops), max(pops))}% chance of rain\n"
            f"Forecast updated {forecast_updated}"
        )
        calendar.events.add(event)
    return calendar


def get_gridpoint(lat: float, lon: float) -> dict:
    """
    Returns gridpoint details for the given latitude and longitude.

    Args:
        lat (float): The latitude of the location.
        lon (float): The longitude of the location.

    Returns:
        dict: The properties for the gridpoints for the given latitude and longitude. Notable properties include:
        - forecastHourly: the URL for the hourly forecast data.
        - forecastZone: an URL from which we can derive the alerts zone.
        - timeZone: the timezone for the location.
        - relativeLocation.properties.city: the city for the location.
    """
    print(f"Fetching gridpoint for {lat}, {lon}")
    url = f"https://api.weather.gov/points/{lat},{lon}"
    return fetch_url(url).json()["properties"]


def simplify_gridpoint(lat: float, lon: float) -> Tuple[float, float]:
    """
    Simplifies the latitude and longitude to the lowest precision that still
    returns the same forecast data from the gridpoint.

    Args:
        lat (float): The latitude of the location.
        lon (float): The longitude of the location.

    Returns:
        Tuple[float, float]: The simplified latitude and longitude.
    """
    last_lat, last_lon = lat, lon
    last_forecast = get_gridpoint(lat, lon)["forecastHourly"]
    print(f"Original forecast: {last_forecast}")
    original_precision = max(len(str(lat).split(".")[1]), len(str(lon).split(".")[1]))
    for precision in range(original_precision - 1, 0, -1):
        rounded_lat, rounded_lon = round(lat, precision), round(lon, precision)
        forecast = get_gridpoint(rounded_lat, rounded_lon)["forecastHourly"]
        print(f"Forecast for {rounded_lat}, {rounded_lon}: {forecast}")
        if forecast != last_forecast:
            break
        last_lat, last_lon = rounded_lat, rounded_lon
        last_forecast = forecast
    return (last_lat, last_lon)
