"""
This module defines a Flask web application with several routes for generating weather-related calendar files.
Routes:
    /: Renders the index page.
    /weather.ics: Returns a calendar file with rain forecasts.
    /alerts.ics: Returns a calendar file with weather alerts.
    /bestweather.ics: Returns a calendar file with the best weather forecasts.
    /warm.ics: Returns a calendar file with warm weather forecasts.
    /cool.ics: Returns a calendar file with cool weather forecasts.
    /comfort.ics: Returns a calendar file with comfortable weather forecasts.
    /soloize: Returns a calendar file with past events and attendees removed.
Functions:
    index(): Handles requests to the index page.
    weather(): Handles requests for the rain calendar.
    alerts(): Handles requests for the alerts calendar.
    best_weather(): Handles requests for the best weather calendar.
    warm(): Handles requests for the warm weather calendar.
    cool(): Handles requests for the cool weather calendar.
    comfort(): Handles requests for the comfortable weather calendar.
    soloize(): Handles requests for the soloize calendar.

"""

import datetime
import json
import flask
import ics
import requests

import nws

app = flask.Flask(__name__)

ICS_CONTENT_TYPE = "text/calendar; charset=utf-8"
DEBUG = True
CAL_CONTENT_TYPE = "text/plain; charset=utf-8" if DEBUG else ICS_CONTENT_TYPE


@app.route("/")
def index() -> str:
    """
    Handle the request for the index page.

    This function logs a message indicating that a request for the index page
    has been received and returns the rendered HTML template for the index page.

    Returns:
        str: The rendered HTML content for the index page.
    """
    print("Request for index page received")
    return flask.render_template("index.html")


@app.route("/simplify/<lat_str>,<lon_str>")
def simplify(lat_str: str, lon_str: str) -> str:
    """
    Simplifies the given latitude and longitude strings by parsing and rounding them.

    Args:
        lat_str (str): The latitude as a string.
        lon_str (str): The longitude as a string.

    Returns:
        str: A JSON response containing the simplified latitude and longitude.
    """
    lat, lon = parse_coords(lat_str, lon_str)
    round_lat, round_lon = nws.simplify_gridpoint(lat, lon)
    result = {"latitude": round_lat, "longitude": round_lon}
    return flask.Response(json.dumps(result), content_type="application/json")


@app.route("/<calendar>/<lat_str>,<lon_str>")
def get_calendar(calendar: str, lat_str: str, lon_str: str):
    """
    Retrieves a weather calendar based on the specified type and geographic coordinates.

    Args:
        calendar (str): The type of calendar to retrieve. Currently supports "precip" for precipitation calendar.
        lat_str (str): The latitude as a string. Must be a valid float between -90 and 90.
        lon_str (str): The longitude as a string. Must be a valid float between -180 and 180.

    Returns:
        The requested weather calendar data.

    Raises:
        werkzeug.exceptions.HTTPException: If the latitude or longitude is invalid, or if the calendar type is unknown.
    """
    lat, lon = parse_coords(lat_str, lon_str)
    gridpoint = nws.get_gridpoint(lat, lon)
    match calendar:
        case "precip":
            result = nws.get_rain_calendar(gridpoint)
        case _:
            flask.abort(404, "Unknown calendar")
    return flask.Response(result.encode("utf-8"), content_type=CAL_CONTENT_TYPE)


def parse_coords(lat_str, lon_str):
    """
    Parses latitude and longitude strings and converts them to floats.

    Args:
        lat_str (str): The latitude as a string.
        lon_str (str): The longitude as a string.

    Returns:
        tuple: A tuple containing the latitude and longitude as floats.

    Raises:
        werkzeug.exceptions.HTTPException: If the latitude or longitude is invalid.
    """
    try:
        lat = float(lat_str)
        if not -90 <= lat <= 90:
            raise ValueError
    except ValueError:
        flask.abort(400, "Invalid latitude")
    try:
        lon = float(lon_str)
        if not -180 <= lon <= 180:
            raise ValueError
    except ValueError:
        flask.abort(400, "Invalid longitude")
    return lat, lon


@app.route("/weather.ics")
def weather() -> str:
    print("Requesting rain calendar")
    return flask.Response(
        nws.get_rain_calendar().encode("utf-8"),
        content_type=CAL_CONTENT_TYPE,
    )


@app.route("/alerts.ics")
def alerts() -> str:
    print("Requesting alerts")
    return flask.Response(nws.get_alert_calendar().encode("utf-8"), content_type=CAL_CONTENT_TYPE)


@app.route("/bestweather.ics")
def best_weather() -> str:
    print("Requesting best weather")
    return flask.Response(
        nws.get_best_weather_calendar().encode("utf-8"), content_type=CAL_CONTENT_TYPE
    )


@app.route("/warm.ics")
def warm() -> str:
    print("Requesting warm weather")
    return flask.Response(nws.get_warm_calendar().encode("utf-8"), content_type=CAL_CONTENT_TYPE)


@app.route("/cool.ics")
def cool() -> str:
    print("Requesting cool weather")
    return flask.Response(nws.get_cool_calendar().encode("utf-8"), content_type=CAL_CONTENT_TYPE)


@app.route("/comfort.ics")
def comfort() -> str:
    print("Requesting comfortable weather")
    return flask.Response(nws.get_comfort_calendar().encode("utf-8"), content_type=CAL_CONTENT_TYPE)


@app.route("/soloize")
def soloize() -> str:
    """
    Handle requests for the soloize calendar.
    
    This endpoint takes a URL parameter pointing to an ICS feed and returns a modified
    version of that feed with:
    - Past events removed
    - All attendees removed from all events
    
    Returns:
        str: The modified ICS calendar as a string.
    """
    print("Requesting soloize calendar")
    url = flask.request.args.get('url')
    if not url:
        flask.abort(400, "Missing 'url' parameter")
    
    # Validate URL to prevent SSRF attacks
    from urllib.parse import urlparse
    parsed_url = urlparse(url)
    
    # Only allow http and https schemes
    if parsed_url.scheme not in ('http', 'https'):
        flask.abort(400, "Only HTTP and HTTPS URLs are allowed")
    
    # Prevent access to localhost and private IP ranges
    hostname = parsed_url.hostname
    if not hostname:
        flask.abort(400, "Invalid URL")
    
    # Block localhost
    if hostname.lower() in ('localhost', '127.0.0.1', '::1'):
        flask.abort(400, "Access to localhost is not allowed")
    
    # Block private IP ranges (basic check)
    if hostname.startswith('192.168.') or hostname.startswith('10.') or hostname.startswith('172.'):
        flask.abort(400, "Access to private IP addresses is not allowed")
    
    try:
        # Fetch the ICS feed from the provided URL
        response = requests.get(url, timeout=30)
        response.raise_for_status()
    except requests.RequestException as err:
        print(f"Error fetching ICS feed: {err}")
        flask.abort(400, f"Failed to fetch ICS feed: {str(err)}")
    
    try:
        # Parse the ICS content
        calendar = ics.Calendar(response.text)
    except Exception as err:
        print(f"Error parsing ICS feed: {err}")
        flask.abort(400, f"Failed to parse ICS feed: {str(err)}")
    
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
    
    return flask.Response(
        new_calendar.serialize().encode("utf-8"),
        content_type=CAL_CONTENT_TYPE
    )


if __name__ == "__main__":
    app.run()
